import { FormEvent, useState } from "react";

import "./App.css";

type InventoryItem = {
  id: string;
  part_num: string;
  part_name: string;
  color_id: number;
  color_name: string;
  expected_qty: number;
  inventory_class: string;
  session_quantity: number;
  session_revision: number;
  global_quantity: number;
};

type CountingSession = { id: string; label: string; status: string };

function _sessionLabels(areas: string): string[] | undefined {
  const labels = areas.split(",").map((value) => value.trim()).filter(Boolean);
  return labels.length > 0 ? labels : undefined;
}

function App() {
  const [setNumber, setSetNumber] = useState("75978");
  const [label, setLabel] = useState("Winkelgasse");
  const [areas, setAreas] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [sessions, setSessions] = useState<CountingSession[]>([]);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [selectedColorId, setSelectedColorId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [message, setMessage] = useState("CSV-Testinventar importieren oder ein eigenes Projekt anlegen.");

  async function loadCountingData(nextProjectId: string, nextSessionId?: string) {
    const sessionsResponse = await fetch(`/api/v1/projects/${nextProjectId}/sessions`);
    const sessionData = await sessionsResponse.json();
    if (!sessionsResponse.ok || sessionData.data.length === 0) throw new Error();
    const sessionId = nextSessionId ?? sessionData.data[0].id;
    const inventoryResponse = await fetch(`/api/v1/projects/${nextProjectId}/inventory?session_id=${sessionId}`);
    const inventory = await inventoryResponse.json();
    if (!inventoryResponse.ok) throw new Error();
    setProjectId(nextProjectId);
    setSessions(sessionData.data);
    setSelectedSessionId(sessionId);
    setItems(inventory.data.items);
  }

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
        body: JSON.stringify({ set_num: setNumber, label, session_labels: _sessionLabels(areas) }),
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
      await loadCountingData(project.data.id);
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
        body: JSON.stringify({ set_num: setNumber, label, session_labels: _sessionLabels(areas) }),
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
      await loadCountingData(project.data.id);
      setMessage(
        imported.data.imported
          ? `${imported.data.requirements} Positionen wurden von Rebrickable importiert.`
          : `${imported.data.requirements} Positionen wurden aus dem lokalen Rebrickable-Cache übernommen.`,
      );
    } catch (error) {
      setMessage(error instanceof Error && error.message ? error.message : "Der Rebrickable-Import ist fehlgeschlagen.");
    }
  }

  async function selectSession(sessionId: string) {
    if (!projectId) return;
    try {
      await loadCountingData(projectId, sessionId);
    } catch {
      setMessage("Der Bereich konnte nicht geladen werden.");
    }
  }

  async function adjust(item: InventoryItem, delta: number) {
    if (!selectedSessionId || !projectId) return;
    try {
      const response = await fetch(`/api/v1/sessions/${selectedSessionId}/counts/adjust`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ inventory_item_id: item.id, delta, client_mutation_id: crypto.randomUUID() }),
      });
      if (!response.ok) throw new Error();
      await loadCountingData(projectId, selectedSessionId);
    } catch {
      setMessage("Die Zählung konnte nicht gespeichert werden.");
    }
  }

  async function setQuantity(item: InventoryItem, quantity: number) {
    if (!selectedSessionId || !projectId || !Number.isInteger(quantity) || quantity < 0) return;
    try {
      const response = await fetch(`/api/v1/sessions/${selectedSessionId}/counts/${item.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ quantity, expected_revision: item.session_revision, client_mutation_id: crypto.randomUUID() }),
      });
      if (!response.ok) throw new Error();
      await loadCountingData(projectId, selectedSessionId);
    } catch {
      setMessage("Die Menge wurde parallel geändert. Bitte erneut versuchen.");
      await loadCountingData(projectId, selectedSessionId);
    }
  }

  const colors = Array.from(new Map(items.map((item) => [item.color_id, item.color_name])).entries());
  const visibleItems = items.filter((item) => (
    (selectedColorId === null || item.color_id === selectedColorId)
    && `${item.part_num} ${item.part_name}`.toLowerCase().includes(search.toLowerCase())
  ));

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
          <label htmlFor="areas">Bereiche (optional, durch Komma getrennt)</label>
          <input id="areas" value={areas} placeholder="z. B. Anleitung 1, Anleitung 2" onChange={(event) => setAreas(event.target.value)} />
          <label htmlFor="inventory-file">CSV-Inventar</label>
          <input id="inventory-file" type="file" accept=".csv,text/csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          <button type="submit">Inventar importieren</button>
          <button type="button" onClick={importFromRebrickable}>Von Rebrickable importieren</button>
        </form>
        <p aria-live="polite">{message}</p>
        {projectId && selectedSessionId && (
          <section className="zaehlbereich" aria-label="Zählbereich">
            <h2>Bereich auswählen</h2>
            <div className="tabs" role="tablist" aria-label="Zählbereiche">
              {sessions.map((session) => <button type="button" role="tab" aria-selected={session.id === selectedSessionId} onClick={() => selectSession(session.id)} key={session.id}>{session.label}</button>)}
            </div>
            <div className="filterbar">
              <label>Suche<input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Teilenummer oder Name" /></label>
              <label>Farbe<select value={selectedColorId ?? ""} onChange={(event) => setSelectedColorId(event.target.value ? Number(event.target.value) : null)}><option value="">Alle Farben</option>{colors.map(([id, name]) => <option key={id} value={id}>Nur: {name}</option>)}</select></label>
              {selectedColorId !== null && <button type="button" onClick={() => setSelectedColorId(null)}>Filter zurücksetzen</button>}
            </div>
            <p className="hinweis">Die Sollmenge gilt für das ganze Set, nicht pro Bereich.</p>
            <table><thead><tr><th>Teil</th><th>Farbe</th><th>Soll gesamt</th><th>Ist Bereich</th><th>Ist gesamt</th><th>Abweichung</th><th>Zählen</th></tr></thead><tbody>{visibleItems.map((item) => {
              const delta = item.global_quantity - item.expected_qty;
              return <tr key={item.id}><td>{item.part_num} – {item.part_name}</td><td>{item.color_name}</td><td>{item.expected_qty}</td><td>{item.session_quantity}</td><td>{item.global_quantity}</td><td>{delta > 0 ? `Überschuss +${delta}` : delta < 0 ? `Vorläufig offen ${-delta}` : "Ausgeglichen"}</td><td><button type="button" aria-label={`-1 ${item.part_num} ${item.color_name}`} onClick={() => adjust(item, -1)}>−</button><input aria-label={`Menge ${item.part_num} ${item.color_name}`} type="number" min="0" value={item.session_quantity} onChange={(event) => setQuantity(item, Number(event.target.value))} /><button type="button" aria-label={`+1 ${item.part_num} ${item.color_name}`} onClick={() => adjust(item, 1)}>+</button></td></tr>;
            })}</tbody></table>
          </section>
        )}
      </section>
    </main>
  );
}

export default App;
