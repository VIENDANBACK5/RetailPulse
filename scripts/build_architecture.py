"""Editable draw.io and SVG overview of the implemented core (no raster mocks)."""
from pathlib import Path
import html
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NODES = [
    ("file", 65, 80, 310, 80, "UCI historical file", "Official CSV / Excel · GBP", "#eff7fa"),
    ("db", 445, 80, 310, 80, "PostgreSQL OLTP", "DEMO orders + order_items · VND", "#eff7fa"),
    ("api", 825, 80, 310, 80, "REST inventory API", "HN / DN / SG · one DEMO server", "#eff7fa"),
    ("ingest", 445, 220, 310, 70, "Python ingestion", "Source identity + manifest + status", "#eaf4ef"),
    ("raw", 445, 340, 310, 70, "MinIO / local Raw", "Manifest SHA256 + local lineage mirror", "#eaf4ef"),
    ("etl", 445, 460, 310, 80, "Validate / transform / load", "Upsert + exact-key SQL reconciliation", "#eaf4ef"),
    ("reject", 825, 460, 310, 80, "Rejected records", "Original row + validation reasons", "#fff1e7"),
    ("dwh", 445, 600, 310, 110, "PostgreSQL Star Schema", "Sales / Inventory facts\nDate / Customer / Product / Branch / Source", "#e9f3fa"),
    ("airflow", 65, 220, 310, 145, "Airflow orchestration", "Collect / load / mine / verify\nFrozen input + retries + DAG logs\nOperations / historical / mining / replay", "#f1f1f8"),
    ("registry", 65, 405, 310, 150, "Run registry and audit", "run_id / batch_id / source status\nPENDING / RUNNING / SUCCESS\nPARTIAL / FAILED + lineage", "#f1f1f8"),
    ("olap", 65, 790, 310, 95, "OLAP / semantic SQL", "Roll-up / drill-down / slice / dice\nPivot / drill-through / source lineage", "#eaf4ef"),
    ("mining", 445, 790, 310, 95, "RFM experiments", "Rules baseline / K2..6 / 10 seeds\nStability / profiles / future holdout", "#f2edf7"),
    ("model", 825, 790, 310, 95, "Persisted mining results", "Model + scaler + metrics + provenance\nCustomer segment snapshots by run", "#f2edf7"),
    ("web", 65, 960, 690, 85, "FastAPI control plane + web BI", "Real background execution, actual DWH queries, logs and artifacts", "#eaf4ef"),
    ("powerbi", 825, 960, 310, 85, "Power BI: Desktop BLOCKED", "Semantic Model + DAX implemented\nReport / refresh not verified", "#fff1e7"),
]
EDGES = [("file", "ingest"), ("db", "ingest"), ("api", "ingest"), ("ingest", "raw"),
         ("raw", "etl"), ("etl", "reject"), ("etl", "dwh"), ("dwh", "olap"),
         ("dwh", "mining"), ("mining", "model"), ("olap", "web"), ("model", "web"),
         ("model", "powerbi"), ("registry", "etl"), ("registry", "mining"),
         ("airflow", "ingest"), ("airflow", "mining")]


def main():
    target = ROOT / "docs/architecture"
    target.mkdir(exist_ok=True)
    root = ET.Element("mxfile", host="app.diagrams.net")
    graph = ET.SubElement(ET.SubElement(root, "diagram", name="Verified core v4"), "mxGraphModel", pageWidth="1200", pageHeight="1100")
    cells = ET.SubElement(graph, "root")
    ET.SubElement(cells, "mxCell", id="0")
    ET.SubElement(cells, "mxCell", id="1", parent="0")
    title = ET.SubElement(cells, "mxCell", id="title", value="RETAILPULSE — IMPLEMENTED CORE ARCHITECTURE", style="text;html=1;fontSize=25;fontStyle=1;", vertex="1", parent="1")
    ET.SubElement(title, "mxGeometry", x="40", y="15", width="1120", height="40", **{"as": "geometry"})
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1100" viewBox="0 0 1200 1100">',
           '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#466274"/></marker></defs>',
           '<rect width="1200" height="1100" fill="white"/>',
           '<text x="600" y="40" text-anchor="middle" font-family="Segoe UI,Arial" font-size="25" font-weight="bold" fill="#183f58">RETAILPULSE — IMPLEMENTED CORE ARCHITECTURE</text>']
    by_id = {n[0]: n for n in NODES}
    for i, (a, b) in enumerate(EDGES):
        dashed = a in ("registry", "airflow") or b == "powerbi"
        edge = ET.SubElement(cells, "mxCell", id=f"e{i}", source=a, target=b, edge="1", parent="1",
                             style="edgeStyle=orthogonalEdgeStyle;endArrow=block;html=1;strokeColor=#466274;" + ("dashed=1;" if dashed else ""))
        ET.SubElement(edge, "mxGeometry", relative="1", **{"as": "geometry"})
        _, ax, ay, aw, ah, *_ = by_id[a]
        _, bx, by, bw, bh, *_ = by_id[b]
        if abs(ay - by) < 5:
            x1, y1, x2, y2 = ax + aw, ay + ah / 2, bx, by + bh / 2
            points = f"{x1},{y1} {x2},{y2}"
        elif a in ("registry", "airflow"):
            x1, y1, x2, y2 = ax + aw, ay + ah / 2, bx, by + bh / 2
            points = f"{x1},{y1} {x1+25},{y1} {x1+25},{y2} {x2},{y2}"
        else:
            x1, y1, x2, y2 = ax + aw / 2, ay + ah, bx + bw / 2, by
            mid = (y1 + y2) / 2
            points = f"{x1},{y1} {x1},{mid} {x2},{mid} {x2},{y2}"
        svg.append(f'<polyline points="{points}" fill="none" stroke="#466274" stroke-width="1.6" marker-end="url(#arrow)"' + (' stroke-dasharray="6 5"' if dashed else '') + '/>')
    for ident, x, y, w, h, title, details, fill in NODES:
        label = f"<b>{html.escape(title)}</b><br>" + html.escape(details).replace("\n", "<br>")
        cell = ET.SubElement(cells, "mxCell", id=ident, value=label, style=f"rounded=1;whiteSpace=wrap;html=1;fontSize=15;fillColor={fill};strokeColor=#7c9aab;", vertex="1", parent="1")
        ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), **{"as": "geometry"})
        lines = details.split("\n")
        start = y + max(28, (h - 23 * (len(lines) + 1)) / 2 + 18)
        svg.extend([f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="#7c9aab"/>',
                    f'<text x="{x+w/2}" y="{start}" text-anchor="middle" font-family="Segoe UI,Arial" font-size="17" font-weight="bold" fill="#183f58">{html.escape(title)}</text>'])
        for i, line in enumerate(lines):
            svg.append(f'<text x="{x+w/2}" y="{start+24*(i+1)}" text-anchor="middle" font-family="Segoe UI,Arial" font-size="13" fill="#35556a">{html.escape(line)}</text>')
    svg.append('<text x="600" y="1080" text-anchor="middle" font-family="Segoe UI,Arial" font-size="13" fill="#657f8f">Solid lines: implemented data flow. Dashed: observability or Desktop integration pending. 21 Oct 2026.</text></svg>')
    ET.ElementTree(root).write(target / "RetailPulse_HLD_v4.drawio", encoding="utf-8", xml_declaration=True)
    (target / "RetailPulse_HLD_v4.svg").write_text("\n".join(svg), encoding="utf-8")
    print("Created editable HLD v4 and SVG; v3 retained")


if __name__ == "__main__":
    main()
