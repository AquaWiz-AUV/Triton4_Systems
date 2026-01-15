#!/usr/bin/env python3
"""Triton-4 COM Server CLI Management Console."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import Optional

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.live import Live
from rich.table import Table
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Add server directory to path
server_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, server_dir)

# Import database modules directly without importing FastAPI app
import importlib.util

def import_module_from_path(module_name, file_path):
    """Import a module from a file path without triggering __init__.py"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# Import database and models directly
database_path = os.path.join(server_dir, "app", "database.py")
models_path = os.path.join(server_dir, "app", "models.py")

database_module = import_module_from_path("app.database", database_path)
models_module = import_module_from_path("app.models", models_path)

SessionMaker = database_module.SessionMaker
engine = database_module.engine
Command = models_module.Command
CommandStatus = models_module.CommandStatus
DescentCheck = models_module.DescentCheck
Device = models_module.Device
Dive = models_module.Dive
EventLog = models_module.EventLog
Heartbeat = models_module.Heartbeat

# Load environment variables from parent directory
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(env_path)

console = Console()


def format_datetime(dt: Optional[datetime]) -> str:
    """Format datetime for display."""
    if dt is None:
        return "-"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_json(data: Optional[dict]) -> str:
    """Format JSON data for display."""
    if data is None:
        return "-"
    return str(data)


@click.group()
def cli():
    """Triton-4 COM Server Management Console."""
    pass


@cli.command()
def devices():
    """List all devices."""
    asyncio.run(_devices())


async def _devices():
    async with SessionMaker() as session:
        result = await session.execute(select(Device))
        devices_list = result.scalars().all()

        if not devices_list:
            console.print("[yellow]No devices found[/yellow]")
            return

        table = Table(title="Devices")
        table.add_column("MID", style="cyan")
        table.add_column("Firmware", style="green")
        table.add_column("State", style="yellow")
        table.add_column("Last HB Seq", style="magenta")
        table.add_column("Last Seen", style="blue")

        for device in devices_list:
            table.add_row(
                device.mid,
                device.fw,
                device.last_state,
                str(device.last_hb_seq) if device.last_hb_seq else "-",
                format_datetime(device.last_seen_at),
            )

        console.print(table)


@cli.command()
@click.argument("mid")
def device(mid: str):
    """Show detailed information for a specific device."""
    asyncio.run(_device(mid))


async def _device(mid: str):
    async with SessionMaker() as session:
        result = await session.execute(select(Device).where(Device.mid == mid))
        device = result.scalar_one_or_none()

        if not device:
            console.print(f"[red]Device {mid} not found[/red]")
            return

        console.print(f"\n[bold cyan]Device: {device.mid}[/bold cyan]")
        console.print(f"Firmware: {device.fw}")
        console.print(f"State: {device.last_state}")
        console.print(f"Last HB Seq: {device.last_hb_seq or '-'}")
        console.print(f"Last Seen: {format_datetime(device.last_seen_at)}")
        console.print(f"Last Exec Command Seq: {device.last_exec_cmd_seq or '-'}")
        console.print(f"Last Exec Status: {device.last_exec_status or '-'}")
        console.print(f"\n[bold]Position:[/bold] {format_json(device.last_pos)}")
        console.print(f"[bold]Power:[/bold] {format_json(device.last_pwr)}")
        console.print(f"[bold]Environment:[/bold] {format_json(device.last_env)}")
        console.print(f"[bold]Network:[/bold] {format_json(device.last_net)}")
        console.print(f"[bold]Recovery Reason:[/bold] {format_json(device.recovery_reason)}")


@cli.command()
@click.argument("mid")
@click.option("--limit", "-n", default=20, help="Number of heartbeats to show")
def heartbeats(mid: str, limit: int):
    """Show heartbeat history for a device."""
    asyncio.run(_heartbeats(mid, limit))


async def _heartbeats(mid: str, limit: int):
    async with SessionMaker() as session:
        result = await session.execute(
            select(Heartbeat)
            .where(Heartbeat.mid == mid)
            .order_by(Heartbeat.hb_seq.desc())
            .limit(limit)
        )
        hbs = result.scalars().all()

        if not hbs:
            console.print(f"[yellow]No heartbeats found for {mid}[/yellow]")
            return

        table = Table(title=f"Heartbeats for {mid} (latest {limit})")
        table.add_column("HB Seq", style="cyan")
        table.add_column("Timestamp (UTC)", style="green")
        table.add_column("Received At", style="blue")
        table.add_column("State", style="yellow")

        for hb in hbs:
            state = hb.payload.get("state", "-")
            table.add_row(
                str(hb.hb_seq),
                format_datetime(hb.ts_utc),
                format_datetime(hb.received_at),
                state,
            )

        console.print(table)


@cli.command()
@click.argument("mid")
@click.option("--limit", "-n", default=20, help="Number of commands to show")
def commands(mid: str, limit: int):
    """Show command history for a device."""
    asyncio.run(_commands(mid, limit))


async def _commands(mid: str, limit: int):
    async with SessionMaker() as session:
        result = await session.execute(
            select(Command)
            .where(Command.mid == mid)
            .order_by(Command.seq.desc())
            .limit(limit)
        )
        cmds = result.scalars().all()

        if not cmds:
            console.print(f"[yellow]No commands found for {mid}[/yellow]")
            return

        table = Table(title=f"Commands for {mid} (latest {limit})")
        table.add_column("Seq", style="cyan")
        table.add_column("Command", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Created At", style="blue")
        table.add_column("Updated At", style="magenta")

        for cmd in cmds:
            table.add_row(
                str(cmd.seq),
                cmd.cmd,
                cmd.status.value,
                format_datetime(cmd.created_at),
                format_datetime(cmd.updated_at),
            )

        console.print(table)


@cli.command()
@click.argument("mid")
@click.option("--depth", "-d", default=100, help="Target depth in meters")
@click.option("--hold", "-h", default=60, help="Hold time at depth in seconds")
@click.option("--cycles", "-c", default=1, help="Number of dive cycles")
def send_command(mid: str, depth: int, hold: int, cycles: int):
    """Send RUN_DIVE command to a device."""
    asyncio.run(_send_command(mid, depth, hold, cycles))


async def _send_command(mid: str, depth: int, hold: int, cycles: int):
    async with SessionMaker() as session:
        # Check if device exists
        result = await session.execute(select(Device).where(Device.mid == mid))
        device = result.scalar_one_or_none()

        if not device:
            console.print(f"[red]Device {mid} not found[/red]")
            return

        # Get next command sequence number
        result = await session.execute(
            select(Command.seq).where(Command.mid == mid).order_by(Command.seq.desc()).limit(1)
        )
        last_seq = result.scalar_one_or_none()
        next_seq = (last_seq or 0) + 1

        # Create command
        cmd = Command(
            mid=mid,
            seq=next_seq,
            cmd="RUN_DIVE",
            args={
                "target_depth_m": depth,
                "hold_at_depth_s": hold,
                "cycles": cycles,
            },
            status=CommandStatus.QUEUED,
            issued_by="cli",
        )
        session.add(cmd)
        await session.commit()

        console.print(f"[green]Command sent successfully![/green]")
        console.print(f"MID: {mid}")
        console.print(f"Seq: {next_seq}")
        console.print(f"Command: RUN_DIVE")
        console.print(f"Target Depth: {depth}m")
        console.print(f"Hold at Depth: {hold}s")
        console.print(f"Cycles: {cycles}")


@cli.command()
@click.argument("mid")
@click.option("--limit", "-n", default=20, help="Number of dives to show")
def dives(mid: str, limit: int):
    """Show dive history for a device."""
    asyncio.run(_dives(mid, limit))


async def _dives(mid: str, limit: int):
    async with SessionMaker() as session:
        result = await session.execute(
            select(Dive)
            .where(Dive.mid == mid)
            .order_by(Dive.created_at.desc())
            .limit(limit)
        )
        dives_list = result.scalars().all()

        if not dives_list:
            console.print(f"[yellow]No dives found for {mid}[/yellow]")
            return

        table = Table(title=f"Dives for {mid} (latest {limit})")
        table.add_column("ID", style="cyan")
        table.add_column("Cmd Seq", style="green")
        table.add_column("OK", style="yellow")
        table.add_column("Started At", style="blue")
        table.add_column("Ended At", style="magenta")

        for dive in dives_list:
            ok_status = "✓" if dive.ok else "✗" if dive.ok is False else "-"
            table.add_row(
                str(dive.id),
                str(dive.cmd_seq),
                ok_status,
                format_datetime(dive.started_at),
                format_datetime(dive.ended_at),
            )

        console.print(table)


@cli.command()
@click.option("--limit", "-n", default=50, help="Number of events to show")
@click.option("--mid", "-m", help="Filter by device MID")
def events(limit: int, mid: Optional[str]):
    """Show event log."""
    asyncio.run(_events(limit, mid))


async def _events(limit: int, mid: Optional[str]):
    async with SessionMaker() as session:
        query = select(EventLog).order_by(EventLog.created_at.desc()).limit(limit)
        if mid:
            query = query.where(EventLog.mid == mid)

        result = await session.execute(query)
        events_list = result.scalars().all()

        if not events_list:
            console.print("[yellow]No events found[/yellow]")
            return

        table = Table(title=f"Event Log (latest {limit})")
        table.add_column("ID", style="cyan")
        table.add_column("MID", style="green")
        table.add_column("Event Type", style="yellow")
        table.add_column("Created At", style="blue")

        for event in events_list:
            table.add_row(
                str(event.id),
                event.mid or "-",
                event.event_type,
                format_datetime(event.created_at),
            )

        console.print(table)


@cli.command()
@click.argument("mid", required=False)
@click.option("--interval", "-i", default=2, help="Update interval in seconds")
def watch(mid: Optional[str], interval: int):
    """Real-time monitoring dashboard for devices."""
    asyncio.run(_watch(mid, interval))


async def _watch(mid: Optional[str], interval: int):
    """Real-time monitoring dashboard."""

    async def generate_table() -> Table:
        async with SessionMaker() as session:
            if mid:
                result = await session.execute(select(Device).where(Device.mid == mid))
                devices_list = [result.scalar_one_or_none()]
                if not devices_list[0]:
                    devices_list = []
            else:
                result = await session.execute(select(Device))
                devices_list = result.scalars().all()

            table = Table(title=f"Triton-4 Device Monitor - {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")
            table.add_column("MID", style="cyan")
            table.add_column("FW", style="green")
            table.add_column("State", style="yellow")
            table.add_column("HB Seq", style="magenta")
            table.add_column("Last Seen", style="blue")
            table.add_column("Cmd Seq", style="red")
            table.add_column("Status", style="white")

            for device in devices_list:
                # Calculate time since last seen
                if device.last_seen_at:
                    delta = datetime.now(timezone.utc) - device.last_seen_at
                    seconds_ago = int(delta.total_seconds())
                    last_seen = f"{seconds_ago}s ago"
                else:
                    last_seen = "-"

                table.add_row(
                    device.mid,
                    device.fw,
                    device.last_state,
                    str(device.last_hb_seq) if device.last_hb_seq else "-",
                    last_seen,
                    str(device.last_exec_cmd_seq) if device.last_exec_cmd_seq else "-",
                    device.last_exec_status or "-",
                )

            return table

    try:
        with Live(console=console, refresh_per_second=1) as live:
            while True:
                table = await generate_table()
                live.update(table)
                await asyncio.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitoring stopped[/yellow]")


@cli.command()
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
def reset_db(force: bool):
    """Delete all data from the database (DANGEROUS!)."""
    asyncio.run(_reset_db(force))


async def _reset_db(force: bool):
    """Delete all records from all tables."""
    if not force:
        console.print("[bold red]⚠️  WARNING: This will delete ALL data from the database![/bold red]")
        console.print("This includes:")
        console.print("  • All devices")
        console.print("  • All heartbeats")
        console.print("  • All commands")
        console.print("  • All dives")
        console.print("  • All descent checks")
        console.print("  • All event logs")
        
        confirm = click.prompt(
            "\nType 'DELETE' to confirm",
            type=str,
            default="",
        )
        
        if confirm != "DELETE":
            console.print("[yellow]Operation cancelled[/yellow]")
            return

    async with SessionMaker() as session:
        # List of tables to delete in order (to avoid foreign key constraints)
        tables_to_delete = [
            (EventLog, "event logs"),
            (DescentCheck, "descent checks"),
            (Dive, "dives"),
            (Command, "commands"),
            (Heartbeat, "heartbeats"),
            (Device, "devices"),
        ]
        
        for model, name in tables_to_delete:
            try:
                await session.execute(model.__table__.delete())
                console.print(f"[yellow]Deleted all {name}[/yellow]")
            except Exception as e:
                console.print(f"[yellow]Skipped {name} (table may not exist): {e}[/yellow]")
        
        try:
            await session.commit()
            console.print("\n[bold green]✓ Database reset complete![/bold green]")
        except Exception as e:
            await session.rollback()
            console.print(f"[bold red]Error committing changes: {e}[/bold red]")
            raise


if __name__ == "__main__":
    cli()
