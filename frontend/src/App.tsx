import { FormEvent, useState } from "react";

import "./App.css";

type InventoryItem = { part_num: string; part_name: string; color_name: string; expected_qty: number; inventory_class: string };

function App() {
  const [setNumber, setSetNumber] = useState("75978");
  const [label, setLabel] = useState("Winkelgasse");
  const [file, setFile] = useState<File | null>(null);
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [message, setMessage] = useState("CSV-Testinventar importieren oder ein eigenes Projekt anlegen.");

  async function importInventory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setMessage("Bitte wähle eine CSV-Datei aus.");
      return;
    }
    setMessage("Import läuft …");
    try {
      const projectResponse = await fetch("/api/v1/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ set_num: setNumber, label }),
      });
      const project = await projectResponse.json();
      if (!projectResponse.ok) throw new Error();
      const data = new FormData();
      data.append("file", file);
      const importResponse = await fetch(`/api/v1/projects/${project.data.id}/import/csv`, {
        method: "POST",
        body: data,
      });
      const imported = await importResponse.json();
      if (!importResponse.ok) throw new Error();
      const inventoryResponse = await fetch(`/api/v1/projects/${project.data.id}/inventory`);
      const inventory = await inventoryResponse.json();
      if (!inventoryResponse.ok) throw new Error();
      setItems(inventory.data.items);
      setMessage(`${imported.data.requirements} Positionen wurden importiert.`);
    } catch {
      setMessage("Der Import ist fehlgeschlagen. Bitte prüfe die CSV-Datei.");
    }
  }

  async function importFromRebrickable() {
    setMessage("Rebrickable-Import läuft …");
    try {
      const projectResponse = await fetch("/api/v1/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ set_num: setNumber, label }),
      });
      const project = await projectResponse.json();
      if (!projectResponse.ok) throw new Error();
      const importResponse = await fetch(`/api/v1/projects/${project.data.id}/import/rebrickable`, {
        method: "POST",
      });
      const importBody = await importResponse.text();
      let imported: { data: { requirements: number; imported: boolean }; detail?: string };
      try {
        imported = JSON.parse(importBody);
      } catch {
        throw new Error("Der Rebrickable-Import wurde nicht rechtzeitig beantwortet. Bitte erneut klicken; ein abgeschlossener Import wird aus dem lokalen Cache übernommen.");
      }
      if (!importResponse.ok) throw new Error(imported.detail);
      const inventoryResponse = await fetch(`/api/v1/projects/${project.data.id}/inventory`);
      const inventory = await inventoryResponse.json();
      if (!inventoryResponse.ok) throw new Error();
      setItems(inventory.data.items);
      setMessage(
        imported.data.imported
          ? `${imported.data.requirements} Positionen wurden von Rebrickable importiert.`
          : `${imported.data.requirements} Positionen wurden aus dem lokalen Rebrickable-Cache übernommen.`,
      );
    } catch (error) {
      setMessage(error instanceof Error && error.message ? error.message : "Der Rebrickable-Import ist fehlgeschlagen.");
    }
  }

  return (
    <main className="startseite">
      <section aria-labelledby="seitentitel">
        <p className="kicker">Set-Inventur</p>
        <h1 id="seitentitel">LEGO Inventur</h1>
        <p>Lege ein Projekt an und importiere ein CSV-Testinventar.</p>
        <p><a href="/synthetic_inventory.csv" download>Synthetische Test-CSV herunterladen</a></p>
        <form onSubmit={importInventory}>
          <label htmlFor="set-number">Set-Nummer auf dem Karton</label>
          <input id="set-number" value={setNumber} onChange={(event) => setSetNumber(event.target.value)} required />
          <label htmlFor="project-label">Projektname</label>
          <input id="project-label" value={label} onChange={(event) => setLabel(event.target.value)} required />
          <label htmlFor="inventory-file">CSV-Inventar</label>
          <input id="inventory-file" type="file" accept=".csv,text/csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          <button type="submit">Inventar importieren</button>
          <button type="button" onClick={importFromRebrickable}>Von Rebrickable importieren</button>
        </form>
        <p aria-live="polite">{message}</p>
        {items.length > 0 && <table><thead><tr><th>Teil</th><th>Farbe</th><th>Soll</th><th>Klasse</th></tr></thead><tbody>{items.map((item) => <tr key={`${item.part_num}-${item.color_name}-${item.inventory_class}`}><td>{item.part_num} – {item.part_name}</td><td>{item.color_name}</td><td>{item.expected_qty}</td><td>{item.inventory_class === "spare" ? "Ersatzteil" : "Pflichtteil"}</td></tr>)}</tbody></table>}
      </section>
    </main>
  );
}

export default App;
