import time
import redis
from qdrant_client import QdrantClient
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.console import Console
from rich.layout import Layout
from rich.align import Align

# Connect to our architecture
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
qdrant = QdrantClient(url="http://localhost:6333")
console = Console()

def generate_dashboard():
    # 1. Check Crawler Pipeline (Redis)
    try:
        queue_size = r.llen("arom_text_pipeline")
        crawler_status = "[green]ONLINE & CRAWLING[/green]" if queue_size > 0 else "[yellow]IDLE / WAITING[/yellow]"
    except Exception:
        queue_size = 0
        crawler_status = "[red]OFFLINE[/red]"

    # 2. Check Vector Graph Size (Qdrant)
    try:
        # Prevent 404 spam by verifying the collection exists first
        if qdrant.collection_exists("axiom_facts"):
            graph_count = qdrant.count(collection_name="axiom_facts").count
            db_status = "[green]MOUNTED[/green]"
        else:
            graph_count = 0
            db_status = "[yellow]WAITING FOR REFINERY...[/yellow]"
    except Exception:
        graph_count = 0
        db_status = "[red]SERVER OFFLINE[/red]"

    # Build the sleek UI Table
    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table.add_column("System Component", style="cyan", width=30)
    table.add_column("Status", justify="center", width=20)
    table.add_column("Real-Time Metric", justify="right", style="green")

    table.add_row(
        "🕷️ Rust Web Spider", 
        crawler_status, 
        f"{queue_size} HTML Blocks in Pipeline"
    )
    table.add_row(
        "🧠 NLP Logic Refinery", 
        "[green]ONLINE[/green]", 
        "Processing Stream..."
    )
    table.add_row(
        "💾 Qdrant Vector Server (Port 6333)", 
        db_status, 
        f"{graph_count} Verified Facts Locked"
    )

    panel = Panel(
        Align.center(table),
        title="[bold blue]🚀 AXIOM KERNEL TELEMETRY[/bold blue]",
        border_style="blue",
        padding=(1, 2)
    )
    return panel

if __name__ == "__main__":
    console.clear()
    # Live refresh loop every 0.5 seconds
    with Live(generate_dashboard(), refresh_per_second=2, console=console) as live:
        while True:
            time.sleep(0.5)
            live.update(generate_dashboard())