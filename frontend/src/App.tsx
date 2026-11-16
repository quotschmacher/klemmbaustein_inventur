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

type CountingSession = { id: string; label: string; status: string; counted_positions: number };
type ProjectSummary = {
  required_sessions_total: number;
  required_sessions_completed: number;
  surplus_types: number;
  provisional_gap_units: number;
  confirmed_missing_units: number;
};
type DifferenceItem = { id: string; part_num: string; part_name: string; color_name: string; missing_quantity: number };
type ReplacementItem = {
  id: string;
  order_id: string;
  requirement_id: string;
  part_num: string;
  part_name: string;
  color_name: string;
  qty_ordered: number;
  qty_received: number;
  qty_booked: number;
  target_session_id: string | null;
  status: string;
};

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
  const [targetSessionId, setTargetSessionId] = useState<string | null>(null);
  const [selectedColorId, setSelectedColorId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [view, setView] = useState<"overview" | "count" | "orders">("overview");
  const [summary, setSummary] = useState<ProjectSummary | null>(null);
  const [surplusItems, setSurplusItems] = useState<Array<{ id: string; part_num: string; part_name: string; color_name: string; surplus_quantity: number }>>([]);
  const [missingItems, setMissingItems] = useState<DifferenceItem[]>([]);
  const [missingFinal, setMissingFinal] = useState(false);
  const [replacements, setReplacements] = useState<ReplacementItem[]>([]);
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
    setTargetSessionId((current) => current ?? sessionId);
    setItems(inventory.data.items);
  }

  async function loadOverview(nextProjectId: string) {
    const [summaryResponse, surplusResponse] = await Promise.all([
      fetch(`/api/v1/projects/${nextProjectId}/summary`),
      fetch(`/api/v1/projects/${nextProjectId}/differences?type=surplus`),
    ]);
    const summaryData = await summaryResponse.json();
    const surplusData = await surplusResponse.json();
    if (!summaryResponse.ok || !surplusResponse.ok) throw new Error();
    setSummary(summaryData.data);
    setSurplusItems(surplusData.data.items);
  }

  async function loadOrders(nextProjectId: string) {
    const [missingResponse, replacementsResponse] = await Promise.all([
      fetch(`/api/v1/projects/${nextProjectId}/differences?type=missing`),
      fetch(`/api/v1/projects/${nextProjectId}/replacements`),
    ]);
    const missingData = await missingResponse.json();
    const replacementsData = await replacementsResponse.json();
    if (!missingResponse.ok || !replacementsResponse.ok) throw new Error();
    setMissingFinal(missingData.data.final);
    setMissingItems(missingData.data.items);
    setReplacements(replacementsData.data);
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
      await loadOverview(project.data.id);
      await loadOrders(project.data.id);
      setView("overview");
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
      await loadOverview(project.data.id);
      await loadOrders(project.data.id);
      setView("overview");
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
      await loadOverview(projectId);
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
      await loadOverview(projectId);
    } catch {
      setMessage("Die Menge wurde parallel geändert. Bitte erneut versuchen.");
      await loadCountingData(projectId, selectedSessionId);
    }
  }

  async function setSessionStatus(session: CountingSession, nextStatus: "completed" | "in_progress") {
    if (!projectId) return;
    if (nextStatus === "completed" && !window.confirm(`Bereich „${session.label}“ wirklich abschließen? Danach sind Zählungen gesperrt, bis du ihn wieder öffnest.`)) return;
    try {
      const response = await fetch(`/api/v1/sessions/${session.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: nextStatus }),
      });
      if (!response.ok) throw new Error();
      await loadCountingData(projectId, selectedSessionId ?? session.id);
      await loadOverview(projectId);
      await loadOrders(projectId);
    } catch {
      setMessage("Der Bereichsstatus konnte nicht gespeichert werden.");
    }
  }

  async function createCombinedReplacement() {
    if (!projectId) return;
    try {
      const response = await fetch(`/api/v1/projects/${projectId}/replacements/from-confirmed-missing`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_session_id: targetSessionId }),
      });
      if (!response.ok) throw new Error();
      await loadOrders(projectId);
    } catch {
      setMessage("Die Sammelbestellung konnte nicht angelegt werden.");
    }
  }

  async function receiveReplacement(item: ReplacementItem, quantity: number) {
    if (!projectId || !Number.isInteger(quantity) || quantity < item.qty_booked) return;
    try {
      const response = await fetch(`/api/v1/projects/${projectId}/replacements/${item.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ qty_received: quantity, status: quantity > 0 ? "received" : "ordered" }),
      });
      if (!response.ok) throw new Error();
      await loadOrders(projectId);
    } catch {
      setMessage("Der Wareneingang konnte nicht gespeichert werden.");
    }
  }

  async function bookReplacement(item: ReplacementItem) {
    if (!projectId || !targetSessionId || item.qty_received <= item.qty_booked) return;
    try {
      const response = await fetch(`/api/v1/replacements/${item.id}/book-into-session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: targetSessionId, quantity: item.qty_received - item.qty_booked, client_mutation_id: crypto.randomUUID() }),
      });
      if (!response.ok) throw new Error();
      await loadCountingData(projectId, targetSessionId);
      await loadOverview(projectId);
      await loadOrders(projectId);
    } catch {
      setMessage("Der Ersatz konnte nicht in den Bereich eingebucht werden.");
    }
  }

  function startNewProject() {
    setProjectId(null);
    setSelectedSessionId(null);
    setSessions([]);
    setItems([]);
    setSummary(null);
    setSurplusItems([]);
    setMissingItems([]);
    setReplacements([]);
    setTargetSessionId(null);
    setSelectedColorId(null);
    setSearch("");
    setMessage("Lege ein weiteres Projekt an und importiere dessen Inventar.");
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
        {!projectId && <form onSubmit={importInventory}>
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
        </form>}
        <p aria-live="polite">{message}</p>
        {projectId && selectedSessionId && (
          <section className="arbeitsbereich" aria-label="Projektansicht">
            <nav className="projektnavigation" aria-label="Projektseiten">
              <button type="button" aria-current={view === "overview" ? "page" : undefined} onClick={() => setView("overview")}>Übersicht</button>
              <button type="button" aria-current={view === "count" ? "page" : undefined} onClick={() => setView("count")}>Zählen</button>
              <button type="button" aria-current={view === "orders" ? "page" : undefined} onClick={() => setView("orders")}>Fehlteile & Bestellungen</button>
              <button type="button" onClick={startNewProject}>Neues Set importieren</button>
            </nav>
            {view === "overview" && summary && <section className="uebersicht" aria-label="Gesamtübersicht">
              <h2>Gesamtübersicht</h2>
              <div className="kennzahlen">
                <article><h3>Noch offene Zählbereiche</h3><strong>{summary.required_sessions_total - summary.required_sessions_completed}</strong><span>von {summary.required_sessions_total}</span></article>
                <article><h3>Aktueller globaler Überschuss</h3><strong>{summary.surplus_types}</strong><span>Teilearten</span></article>
                <article><h3>{summary.confirmed_missing_units > 0 ? "Bestätigte Fehlteile" : "Vorläufige Differenz"}</h3><strong>{summary.confirmed_missing_units || summary.provisional_gap_units}</strong><span>{summary.confirmed_missing_units > 0 ? "Teile fehlen" : "noch offen"}</span></article>
              </div>
              <h3>Bereiche</h3>
              <div className="bereichskarten">{sessions.map((session) => <article key={session.id}><h4>{session.label}</h4><p>{session.status === "completed" ? "Abgeschlossen" : "In Bearbeitung"} · {session.counted_positions} Positionen erfasst</p><button type="button" onClick={() => { setView("count"); selectSession(session.id); }}>Fortsetzen</button>{session.status === "completed" ? <button type="button" onClick={() => setSessionStatus(session, "in_progress")}>Wieder öffnen</button> : <button type="button" onClick={() => setSessionStatus(session, "completed")}>Abschließen</button>}</article>)}</div>
              {surplusItems.length > 0 && <section className="differenzen"><h3>Aktueller globaler Überschuss</h3><ul>{surplusItems.map((item) => <li key={item.id}>{item.part_num} – {item.part_name}, {item.color_name}: +{item.surplus_quantity}</li>)}</ul></section>}
            </section>}
            {view === "orders" && <section className="bestellungen" aria-label="Fehlteile und Bestellungen">
              <h2>Fehlteile & Bestellungen</h2>
              <label>Zielbereich (manuelle Zuordnung)<select value={targetSessionId ?? ""} onChange={(event) => setTargetSessionId(event.target.value || null)}><option value="">Noch nicht zuordnen</option>{sessions.map((session) => <option key={session.id} value={session.id}>{session.label}</option>)}</select></label>
              {!missingFinal && <p className="hinweis">Fehlteile werden erst nach Abschluss aller Pflichtbereiche als bestellbar angezeigt. Die aktuelle Differenz ist noch vorläufig.</p>}
              {missingFinal && <section><h3>Bestellbare Fehlteile</h3>{missingItems.length === 0 ? <p>Keine bestätigten Fehlteile.</p> : <><p>Diese Positionen werden gemeinsam als eine Sammelbestellung angelegt.</p><ul className="positionsliste">{missingItems.map((item) => <li key={item.id}><span>{item.part_num} – {item.part_name}, {item.color_name}: {item.missing_quantity} fehlen</span></li>)}</ul><button type="button" onClick={createCombinedReplacement}>Sammelbestellung anlegen ({missingItems.length} Positionen)</button></>}</section>}
              <section><h3>Bestellungen</h3>{replacements.length === 0 ? <p>Noch keine Bestellpositionen.</p> : <ul className="positionsliste">{replacements.map((item) => <li key={item.id}><span>{item.part_num} – {item.part_name}, {item.color_name}: bestellt {item.qty_ordered}, erhalten {item.qty_received}, eingebucht {item.qty_booked}</span><label>Erhalten<input aria-label={`Erhalten ${item.part_num}`} type="number" min={item.qty_booked} value={item.qty_received} onChange={(event) => receiveReplacement(item, Number(event.target.value))} /></label>{item.qty_received > item.qty_booked && <button type="button" onClick={() => bookReplacement(item)}>In Zielbereich einbuchen</button>}</li>)}</ul>}</section>
              <p className="hinweis">Die Zielbereich-Zuordnung ist eine manuelle organisatorische Entscheidung und kein Nachweis, wo das Teil ursprünglich gefehlt hat.</p>
            </section>}
            {view === "count" && <section className="zaehlbereich" aria-label="Zählbereich">
              <h2>Bereich auswählen</h2>
              <div className="tabs" role="tablist" aria-label="Zählbereiche">{sessions.map((session) => <button type="button" role="tab" aria-selected={session.id === selectedSessionId} onClick={() => selectSession(session.id)} key={session.id}>{session.label}</button>)}</div>
              <div className="filterbar"><label>Suche<input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Teilenummer oder Name" /></label><label>Farbe<select value={selectedColorId ?? ""} onChange={(event) => setSelectedColorId(event.target.value ? Number(event.target.value) : null)}><option value="">Alle Farben</option>{colors.map(([id, name]) => <option key={id} value={id}>Nur: {name}</option>)}</select></label>{selectedColorId !== null && <button type="button" onClick={() => setSelectedColorId(null)}>Filter zurücksetzen</button>}</div>
              <p className="hinweis">Die Sollmenge gilt für das ganze Set, nicht pro Bereich.</p>
              <div className="tabellenrahmen"><table><thead><tr><th>Teil</th><th>Farbe</th><th>Soll</th><th>Bereich</th><th>Gesamt</th><th>Abweichung</th><th>Zählen</th></tr></thead><tbody>{visibleItems.map((item) => { const delta = item.global_quantity - item.expected_qty; return <tr key={item.id}><td>{item.part_num} – {item.part_name}</td><td>{item.color_name}</td><td>{item.expected_qty}</td><td>{item.session_quantity}</td><td>{item.global_quantity}</td><td>{delta > 0 ? `Überschuss +${delta}` : delta < 0 ? `Vorläufig offen ${-delta}` : "Ausgeglichen"}</td><td><button type="button" aria-label={`-1 ${item.part_num} ${item.color_name}`} onClick={() => adjust(item, -1)}>−</button><input aria-label={`Menge ${item.part_num} ${item.color_name}`} type="number" min="0" value={item.session_quantity} onChange={(event) => setQuantity(item, Number(event.target.value))} /><button type="button" aria-label={`+1 ${item.part_num} ${item.color_name}`} onClick={() => adjust(item, 1)}>+</button></td></tr>; })}</tbody></table></div>
            </section>}
          </section>
        )}
      </section>
    </main>
  );
}

export default App;
