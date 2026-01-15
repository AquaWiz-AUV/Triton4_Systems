// Triton-LiteRev2 本番用プログラム（大瀬崎試験）- 最適化版v2
// 2025/06/15
// 作者: Ryusei Kamiyama
//============================================================
// ライブラリ
#include <EEPROM.h>
#include <TimeLib.h>
#include <SoftwareSerial.h>
#include <Wire.h>
#include <SD.h>
#include <TinyGPS++.h>
#include <DallasTemperature.h>
#include <OneWire.h>
#include <MS5837.h>
#include <RTC_RX8025NB.h>
#include <IRremote.hpp>
#include <LiquidCrystal_I2C.h>

//============================================================
// リモコンのボタンアドレス定義
#define IR_CMD_ENTER_SENSING_MODE 0x40
#define IR_CMD_ENTER_IDLE_MODE    0x44

// ====== ユーザー設定項目 ======
const char* APN = "soracom.io";
const char* SERVER_URL = "script.google.com";
const char* SERVER_PATH = "/macros/s/AKfycby1kQNUDMgZuvsFSuk2MmAgGHm5OKsDegzIBPYr4UMqkaAY8S_nxFWjjLLsPLnAnlKoVQ/exec";
const int CONTENT_TYPE = 4; // 4: application/json

// 設定構造体
struct {
  uint32_t  supplyStartDelayMs  = 10000;
  uint32_t  supplyStopDelayMs   = 5000;
  uint32_t  exhaustStartDelayMs = 30000;
  uint32_t  exhaustStopDelayMs  = 30000;
  uint8_t   lcdMode             = 0;
  uint8_t   logMode             = 2;
  uint16_t  diveCount           = 0;
  uint16_t  inPressThresh       = 5;
} cfg;

//============================================================
// EEPROM関連
#define MAX_DATA_LENGTH 32
// SDカード関連
char dataFileName[13];
// 水の密度設定
#define FLUID_DENSITY 997

//============================================================
// ピン設定
#define PIN_CS_SD         10
#define PIN_ONEWIRE       4
#define PIN_IN_PRESSURE   A3
#define PIN_LED_GREEN     9
#define PIN_LED_RED       8
#define PIN_VALVE1_SUPPLY  7
#define PIN_VALVE2_EXHAUST 6
#define PIN_VALVE3_PRESS   5
#define PIN_IR_REMOTE     14

SoftwareSerial gpsSerial(2, 3);
SoftwareSerial saramodem(A6, A7);
TinyGPSPlus gps;
MS5837 DepthSensor;
RTC_RX8025NB rtc;
LiquidCrystal_I2C lcd(0x27, 16, 2);

//============================================================
// センサ変数
float noramlTemp;
float prsInternalRaw;
float prsInternalMbar;
float prsExternal;
float prsExternalDepth;
float prsExternalTmp;

//============================================================
// GPSデータ
uint16_t gpsAltitude;
uint8_t gpsSatellites;
float gpsLat, gpsLng;

//============================================================
// RTC変数
uint16_t rtcYear;
uint8_t rtcMonth, rtcDay, rtcHour, rtcMinute, rtcSecond;

//============================================================
// 制御状態変数
unsigned long timeNowMs, timeLastControlMs;
bool isValve1SupplyOpen, isValve2ExhaustOpen, isValve3PressOpen;
bool isControllingValve;
int8_t valveCtrlState = 0; // 1: EXHstart 2: EXHstop 3: SUPstart 0: SUPstop
int8_t movementState; // 1: UP 2: DOWN 3: PRS
unsigned int divedCount = 0;
bool isSensingMode = false;

String RSSI;

//============================================================
// 準備処理
//============================================================
void setup() {
  Serial.begin(9600);
  Wire.begin();
  IrReceiver.begin(PIN_IR_REMOTE, true);


  // 水圧センサ
  DepthSensor.init();

  DepthSensor.setModel(MS5837::MS5837_30BA);
  DepthSensor.setFluidDensity(FLUID_DENSITY);

  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_VALVE1_SUPPLY, OUTPUT);
  pinMode(PIN_VALVE2_EXHAUST, OUTPUT);
  pinMode(PIN_VALVE3_PRESS, OUTPUT);
  pinMode(PIN_CS_SD, OUTPUT);

  while (!SD.begin(PIN_CS_SD)) {
    lcd.clear();
    lcd.setCursor(0,0);
    lcd.print(F("SD FAILED"));
    Serial.println("ERROR: SD FAILED!");
    delay(1000);
  }

  Serial.println(F("ERROR: EEPROM read failed, using defaults"));
  // デフォルト時刻を設定
  rtc.setDateTime(2025, 11, 6, 12, 0, 0);
  // デフォルトファイル名を設定
  sprintf(dataFileName, "lte.csv");

  timeLastControlMs = millis();
  delay(2000);
}

//============================================================
// メイン処理ループ
//============================================================
void loop() {
  timeNowMs = millis();
  
  // IR受信処理
  if (IrReceiver.decode()) {
    IrReceiver.resume();
    if (IrReceiver.decodedIRData.address == 0) {
      uint8_t cmd = IrReceiver.decodedIRData.command;
      if (cmd == IR_CMD_ENTER_SENSING_MODE) {
        isSensingMode = true;
      } else if (cmd == IR_CMD_ENTER_IDLE_MODE) {
        isSensingMode = false;
        divedCount = 0;
        lcd.clear();
        lcd.backlight();
        lcd.print(F("WaitingMode"));
        lcd.setCursor(0,1);
        lcd.print(F("log:"));
        lcd.print(cfg.logMode);
        lcd.print(F(" lcd:"));
        lcd.print(cfg.lcdMode);
      }
    }
  }
  
  if (isSensingMode) {
    digitalWrite(PIN_LED_GREEN, HIGH);
    digitalWrite(PIN_LED_RED, LOW);

    // センサデータ取得
    DepthSensor.read();
    prsExternal = DepthSensor.pressure();
    prsExternalDepth = DepthSensor.depth();
    prsExternalTmp = DepthSensor.temperature();

    prsInternalRaw = analogRead(PIN_IN_PRESSURE);
    float v = prsInternalRaw * 0.00488 - 0.25; // /1024*5を最適化
    prsInternalMbar = v * 6.667; // /4.5*30を最適化
    float prsDiff = (prsInternalMbar * 68.94 + 1013.25) - prsExternal;
    // 加圧制御
    if (prsDiff+cfg.inPressThresh < 0) {
      digitalWrite(PIN_VALVE3_PRESS, HIGH);
      isValve3PressOpen = true;
      isControllingValve = true;
      movementState = 3;
      delay(100);
    } else {
      digitalWrite(PIN_VALVE3_PRESS, LOW);
      isValve3PressOpen = false;
    }
    
    getGPSData();
    getLTEsignalStrength();
    // getTemperatureData();
    ctrlValve();
    handleLcdDisp();
    handleSDcard();
  } else {
    digitalWrite(PIN_LED_GREEN, LOW);
    digitalWrite(PIN_LED_RED, HIGH);
  }
}

//============================================================
// LTE関連
bool sendATCommand(const String& command, const String& expected_response, unsigned long timeout) {
  saramodem.println(command);
  Serial.println("--> " + command);

  unsigned long startTime = millis();
  String response = "";
  while (millis() - startTime < timeout) {
    if (saramodem.available()) {
      char c = saramodem.read();
      response += c;

      if (response.indexOf(expected_response) != -1) {
        Serial.println("<<- " + response);
        return true;
      }
    }
  }
  Serial.println("<<- [TIMEOUT] " + response);
  return false;
}

// HTTPS POST関数
void PostGas() {
  saramodem.begin(9600);
  delay(2000);
  // --- ここから送信データを作成 ---
  // RTCの現在時刻をフォーマット（YYYY/MM/DD hh:mm:ss）
  String cmd;
  char timeBuf[32];
  sprintf(timeBuf, "%04d/%02d/%02d %02d:%02d:%02d", 
          rtcYear, rtcMonth, rtcDay, rtcHour, rtcMinute, rtcSecond);

  // GPSデータが未取得なら「N/A」を入れる
  String latStr = (gps.location.isValid()) ? String(gpsLat, 6) : "0.0";
  String lngStr = (gps.location.isValid()) ? String(gpsLng, 6) : "0.0";
  String altStr = String(gpsAltitude);
  String satStr = String(gpsSatellites);

  // LTE, SD, GPSの状態を文字列で記録（このまま維持）
  String GPS_ERROR_STATE = (gps.location.isValid()) ? "OK" : "N/A";
  String SD_ERROR_STATE  = SD.begin(PIN_CS_SD) ? "OK" : "N/A";
  String LTE_ERROR_STATE = "N/A";  // LTEの結果はATレスポンスで後に取得

  // JSON生成（フォーマットは既存コードと同じ）
  String POST_DATA = 
    "{\"DataType\":\"HK\","
    "\"MachineID\":\"NANO001\","
    "\"MachineTime\":\"" + String(timeBuf) + "\","
    "\"GPS\":{"
      "\"LAT\":" + latStr + ","
      "\"LNG\":" + lngStr + ","
      "\"ALT\":" + altStr + ","
      "\"SAT\":" + satStr +
    "},"
    "\"BAT\":\"N/A\","
    "\"SENSOR\":{"
      "\"DEPTH\":" + String(prsExternalDepth, 2) + ","
      "\"PRESSURE_INT\":" + String(prsInternalMbar * 68.94 + 1013.25, 2) + ","
      "\"PRESSURE_EXT\":" + String(prsExternal, 2) + ","
      "\"TEMP_WATER\":" + String(prsExternalTmp, 2) + ","
      "\"TEMP_BODY\":" + String(noramlTemp, 2) +
    "},"
    "\"CMT\":\"MODE:NORMAL,GPS_ERROR:" + String(GPS_ERROR_STATE) +
    ", SD_ERROR:" + String(SD_ERROR_STATE) +
    ", LTE_ERROR:" + String(LTE_ERROR_STATE) +
    ",RSSI:" + String(RSSI) + "\"}";

  // --- ここまでが送信JSONの組み立て部分 ---
  Serial.println("[JSON Data]");
  Serial.println(POST_DATA);
  Serial.println();
  
  Serial.println("[Step 1] Network Preparation");
  sendATCommand("AT", "OK", 1000);
  if (!sendATCommand("AT+CPIN?", "READY", 5000)) {
    Serial.println("SIM not ready. Halting.");
  }
  sendATCommand("AT+UMNOPROF=20", "OK", 1000);
  sendATCommand("AT+CFUN=1", "OK", 1000);

  // ネットワーク登録待ち
  Serial.println("Waiting for network registration...");
  bool result = sendATCommand("AT+CEREG?", "OK", 15000);
  if (result) {
    Serial.println("Registered to network.");
  }
  delay(2000);

  Serial.println("[Step 2] PDP Context Activation");
  sendATCommand("AT+COPS=2", "OK", 1000);
  cmd = "AT+CGDCONT=1,\"IP\",\"" + String(APN) + "\"";
  sendATCommand(cmd, "OK", 5000);
  cmd = " AT+UAUTHREQ=1,1,\"sora\",\"sora\" ";
  sendATCommand(cmd, "OK", 1000);
  sendATCommand("AT+COPS=0", "OK", 1000);
  // Attach
  sendATCommand("AT+CGATT=1", "OK", 10000);

  // Activate PDP

  while(true) {
    bool result = sendATCommand("AT+CGACT=1,1", "OK", 15000);
    if(result){
      Serial.println("PDP Activated");
      break;
    }
    delay(2000);
  }

  

  // Check IP address
  sendATCommand("AT+CGDCONT?", "OK", 2000);
  cmd = " AT+UDNSRN=0,\"script.google.com\" ";
  sendATCommand(cmd, "OK", 1000);

  

  // --- Step3: HTTPSプロファイル設定 ---
  Serial.println("[Step 3] HTTP Profile Configuration");

  sendATCommand("AT+UHTTP=0,6,1", "OK", 1000);
  sendATCommand("AT+UHTTP=0,5,443", "OK", 1000);
  // cmd = " AT+UHTTP=0,1,\"" + String(SERVER_URL) + "\" ";
  cmd = " AT+UHTTP=0,1,\"" + String(SERVER_URL) + "\" ";
  sendATCommand(cmd, "OK", 5000);

  cmd = "AT+UPING=\"" + String(SERVER_URL) + "\"";
  sendATCommand(cmd, "\nOK", 5000);

  // --- Step4: HTTPS POST ---
  Serial.println("[Step 4] Executing HTTPS POST");

  // First, write the data to a file on the module as it's too long for a single command
  const char* post_filename = "post_data.json";
  sendATCommand("AT+UDELFILE=\"" + String(post_filename) + "\"", "OK", 1000); // Delete old file to be safe

  sendATCommand("AT+UDWNFILE=\"" + String(post_filename) + "\"," + String(POST_DATA.length()), ">", 3000);
  Serial.println("--> AT+UDWNFILE=\"" + String(post_filename) + "\"," + String(POST_DATA.length()));
  sendATCommand(POST_DATA, "\nOK", 3000);
  Serial.println("--> [SENT DATA]");
  delay(1000); // Wait for file to be written and OK response
  
  // Read and discard any response from the file write operation
  while(saramodem.available()) { 
    Serial.write(saramodem.read()); 
  }
  Serial.println();

  // Now, send the POST command that uses the file
  const char* resp_filename = "response.txt";
  sendATCommand("AT+UDELFILE=\"" + String(resp_filename) + "\"", "OK", 1000); // Delete old file to be safe
  cmd = "AT+UHTTPC=0,4,\"" + String(SERVER_PATH) + "\",\"response.txt\",\"" + String(post_filename) + "\"," + String(CONTENT_TYPE);
  sendATCommand(cmd, "\nOK", 20000); // Expect OK, URC comes later. Increased timeout.

  Serial.println("POST command sent.");

  saramodem.end();
}

// LTE信号強度取得関数（化け防止・改良版）
void getLTEsignalStrength() {
  saramodem.begin(9600);
  RSSI = ""; // 前回値クリア

  // 受信バッファをフラッシュ
  while (saramodem.available()) saramodem.read();

  // コマンド送信
  saramodem.println("AT+CSQ");
  Serial.println("--> AT+CSQ");

  unsigned long start = millis();
  while (millis() - start < 2000) {
    if (saramodem.available()) {
      String line = saramodem.readStringUntil('\n');
      line.trim();

      // 「+CSQ:」が含まれていたら保持
      if (line.startsWith("+CSQ:")) {
        RSSI = line;
      }
    }
  }

  if (RSSI == "") RSSI = "NO_RESPONSE";
  Serial.println("<<- RSSI=" + RSSI);
saramodem.end();
}

//============================================================
// センシング関連
void getTemperatureData() {
  OneWire ow(PIN_ONEWIRE);
  DallasTemperature s(&ow);
  s.begin();
  s.requestTemperatures();
  noramlTemp = s.getTempCByIndex(0);
}

void getGPSData() {
  gpsSerial.begin(9600);
  
  unsigned long st = millis();
  while ((millis() - st) < 1000) {
    while (gpsSerial.available()) {
      if (gps.encode(gpsSerial.read())) {
        if (gps.location.isUpdated()) {
          gpsLat = gps.location.lat();
          gpsLng = gps.location.lng();
          gpsAltitude = gps.altitude.meters();
          gpsSatellites = gps.satellites.value();
        }
        if (gps.time.isValid() && gps.date.isValid()) {
          correctTime();
          break;
        }
      }
    }
  }
  gpsSerial.end();
}

void correctTime() {
  if (!gps.time.isValid() || !gps.date.isValid()) return;
  
  int y = gps.date.year();
  int m = gps.date.month();
  int d = gps.date.day();
  int h = gps.time.hour() + 9;
  int mn = gps.time.minute();
  int s = gps.time.second();

  if (h >= 24) { h -= 24; d++; }
  
  uint8_t dim[12] = {31,28,31,30,31,30,31,31,30,31,30,31};
  if (d > dim[m-1]) {
    if (!(m == 2 && d == 29 && ((y%4==0 && y%100!=0) || y%400==0))) {
      d = 1; m++;
    }
  }
  if (m > 12) { m = 1; y++; }

  rtc.setDateTime(y, m, d, h, mn, s);
  
  tmElements_t tm = rtc.read();
  rtcYear = tmYearToCalendar(tm.Year);
  rtcMonth = tm.Month;
  rtcDay = tm.Day;
  rtcHour = tm.Hour;
  rtcMinute = tm.Minute;
  rtcSecond = tm.Second;
}

//============================================================
// 制御関連
void ctrlValve() {
  if (cfg.diveCount <= divedCount && cfg.diveCount != 0) return;
  
  unsigned long dt = timeNowMs - timeLastControlMs;
  
  switch (valveCtrlState) {
    case 0:
      if (dt > cfg.exhaustStartDelayMs) {
        digitalWrite(PIN_VALVE2_EXHAUST, HIGH);
        isValve2ExhaustOpen = true;
        isControllingValve = true;
        valveCtrlState = 1;
        movementState = 2;
        timeLastControlMs = timeNowMs;
        Serial.println("exh start");
      }
      break;
    case 1:
      if (dt > cfg.exhaustStopDelayMs) {
        digitalWrite(PIN_VALVE2_EXHAUST, LOW);
        isValve2ExhaustOpen = false;
        isControllingValve = true;
        valveCtrlState = 2;
        movementState = 2;
        timeLastControlMs = timeNowMs;
        Serial.println("exh stop");
      }
      break;
    case 2:
      if (dt > cfg.supplyStartDelayMs) {
        digitalWrite(PIN_VALVE1_SUPPLY, HIGH);
        isValve1SupplyOpen = true;
        isControllingValve = true;
        valveCtrlState = 3;
        movementState = 1;
        timeLastControlMs = timeNowMs;
        Serial.println("sup start");
      }
      break;
    case 3:
      if (dt > cfg.supplyStopDelayMs) {
        digitalWrite(PIN_VALVE1_SUPPLY, LOW);
        PostGas();
        PostGas();
        isValve1SupplyOpen = false;
        isControllingValve = true;
        valveCtrlState = 0;
        movementState = 1;
        divedCount++;
        timeLastControlMs = timeNowMs;
        Serial.println("sup stop");
      }
      break;
  }
}

//============================================================
// SDカード保存関連
bool handleSDcard() {
  char buf[256]; // 出力バッファ
  char strLat[16], strLng[16], strPinRaw[10], strPinMbar[10], strPout[10];
  char strDepth[10], strExtTmp[10], strTemp[10];

  if (isControllingValve && cfg.logMode != 2 && cfg.logMode != 3) {
    // movementState を文字列に変換
    const char* moveStr = "UNDEF";
    if (movementState == 1) moveStr = "UP";
    else if (movementState == 2) moveStr = "DOWN";
    else if (movementState == 3) moveStr = "PRESSURE";

    sprintf(buf, "%lu,%04d/%02d/%02d-%02d:%02d:%02d,CTRL,MSG,%s,V1SUP,%d,V2EXH,%d,V3PRS,%d",
            timeNowMs, rtcYear, rtcMonth, rtcDay, rtcHour, rtcMinute, rtcSecond,
            moveStr, isValve1SupplyOpen, isValve2ExhaustOpen, isValve3PressOpen);

    File f = SD.open(dataFileName, FILE_WRITE);
    if (f) {
      f.println(buf);
      Serial.println(buf);
      f.close();
    } else {
      lcd.clear();
      lcd.print(F("SD card failed!"));
      delay(3000);
    }
    isControllingValve = false;
  }

  // データログ部
  if (cfg.logMode == 0 || cfg.logMode == 2) {
    // float を文字列へ変換
    dtostrf(gpsLat,         10, 6, strLat);
    dtostrf(gpsLng,         10, 6, strLng);
    dtostrf(prsInternalRaw, 8, 0, strPinRaw);
    dtostrf(prsInternalMbar,5, 1, strPinMbar);
    dtostrf(prsExternal,    5, 1, strPout);
    dtostrf(prsExternalDepth,5,1, strDepth);
    dtostrf(prsExternalTmp, 5, 1, strExtTmp);
    dtostrf(noramlTemp,     5, 1, strTemp);

    sprintf(buf, "%lu,%04d/%02d/%02d-%02d:%02d:%02d,DATA,LAT,%s,LNG,%s,SATNUM,%d,ALT,%d,"
              "PIN_RAW,%s,PIN_MBAR,%s,POUT,%s,POUT_DEPTH,%s,POUT_TMP,%s,TMP,%s,"
              "VCTRL_STATE,%d,MOV_STATE,%d,DIVE_COUNT,%d,RSSI,%s",
        timeNowMs, rtcYear, rtcMonth, rtcDay, rtcHour, rtcMinute, rtcSecond,
        strLat, strLng, gpsSatellites, gpsAltitude,
        strPinRaw, strPinMbar, strPout, strDepth, strExtTmp, strTemp,
        valveCtrlState, movementState, divedCount,
        RSSI.c_str()); // ←ここで呼び出し
  }
  else if (cfg.logMode == 1 || cfg.logMode == 3) {
    dtostrf(prsInternalMbar, 5, 1, strPinMbar);
    dtostrf(prsExternal,     5, 1, strPout);
    dtostrf(prsExternalDepth,5, 1, strDepth);
    dtostrf(prsExternalTmp,  5, 1, strExtTmp);
    dtostrf(noramlTemp,      5, 1, strTemp);

    sprintf(buf, "%lu,%04d/%02d/%02d-%02d:%02d:%02d,DATA,PIN_MBAR,%s,POUT,%s,POUT_DEPTH,%s,POUT_TMP,%s,TMP,%s,VCTRL_STATE,%d,MOV_STATE,%d,DIVE_COUNT,%d,",
            timeNowMs, rtcYear, rtcMonth, rtcDay, rtcHour, rtcMinute, rtcSecond,
            strPinMbar, strPout, strDepth, strExtTmp, strTemp,
            valveCtrlState, movementState, divedCount);
  } else {
    lcd.clear();
    lcd.print(F("logMode UNKNOWN!"));
    return false;
  }

  File f = SD.open(dataFileName, FILE_WRITE);
  if (f) {
    f.println(buf);
    Serial.println(buf);
    f.close();
    return true;
  } else {
    lcd.clear();
    lcd.print(F("SD card failed!"));
    delay(3000);
  }
  return false;
}

//============================================================
// LCD表示関数
void handleLcdDisp() {
  if (isControllingValve && cfg.lcdMode == 1) {
    lcd.clear();
    lcd.print(F("V_CTRL:"));
    lcd.print(movementState==1?F("UP"):movementState==2?F("DOWN"):movementState==3?F("PRESS"):F("UNDEF"));
    lcd.setCursor(0,1);
    lcd.print(F("V1:"));
    lcd.print(isValve1SupplyOpen);
    lcd.print(F(" V2:"));
    lcd.print(isValve2ExhaustOpen);
    lcd.print(F(" V3:"));
    lcd.print(isValve3PressOpen);
  }
  
  switch(cfg.lcdMode) {
    case 0:
      lcd.clear();
      lcd.setCursor(0,0);
      lcd.print(rtcYear);
      lcd.print('/');
      lcd.print(rtcMonth);
      lcd.print('/');
      lcd.print(rtcDay);
      lcd.print(' ');
      lcd.print(rtcHour);
      lcd.print(':');
      lcd.print(rtcMinute);
      lcd.setCursor(0,1);
      lcd.print(rtcSecond);
      lcd.print("sec ");
      lcd.print("dived:");
      lcd.print(divedCount);
      break;
    case 1:
      break;
    case 2:
      lcd.clear();
      lcd.print(F("TMP:"));
      lcd.print(noramlTemp);
      lcd.setCursor(0,1);
      lcd.print(F("DepthTMP:"));
      lcd.print(prsExternalTmp);
      break;
    case 3:
      lcd.clear();
      lcd.print(F("PrsExt:"));
      lcd.print(prsExternal);
      lcd.setCursor(0,1);
      lcd.print(F("PrsInt:"));
      lcd.print(prsInternalMbar * 68.94 + 1013.25);
      break;
    default:
      lcd.noBacklight();
      break;
  }
}

//============================================================


//============================================================

