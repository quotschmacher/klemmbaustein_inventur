import { FormEvent, useState } from "react";

import "./App.css";

function App() {
  const [setNumber, setSetNumber] = useState("75978-1");
  const [label, setLabel] = useState("Winkelgasse");
  const [file, setFile] = useState<File | null>(null);
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
      setMessage(`${imported.data.requirements} Positionen wurden importiert.`);
    } catch {
      setMessage("Der Import ist fehlgeschlagen. Bitte prüfe die CSV-Datei.");
    }
  }

  return (
    <main className="startseite">
      <section aria-labelledby="seitentitel">
        <p className="kicker">Set-Inventur</p>
        <h1 id="seitentitel">LEGO Inventur</h1>
        <p>Lege ein Projekt an und importiere ein CSV-Testinventar.</p>
        <form onSubmit={importInventory}>
          <label htmlFor="set-number">Set-Nummer</label>
          <input id="set-number" value={setNumber} onChange={(event) => setSetNumber(event.target.value)} required />
          <label htmlFor="project-label">Projektname</label>
          <input id="project-label" value={label} onChange={(event) => setLabel(event.target.value)} required />
          <label htmlFor="inventory-file">CSV-Inventar</label>
          <input id="inventory-file" type="file" accept=".csv,text/csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          <button type="submit">Inventar importieren</button>
        </form>
        <p aria-live="polite">{message}</p>
      </section>
    </main>
  );
}

export default App;
