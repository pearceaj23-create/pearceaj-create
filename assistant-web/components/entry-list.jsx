import { deleteLifeEntry, setEntryStatus } from "@/app/assistant/actions";

function formatDate(value) {
  if (!value) return null;
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(new Date(value));
}

export default function EntryList({ entries = [], empty = "Nothing here yet. Add a note when you are ready." }) {
  if (!entries.length) return <div className="empty-state">{empty}</div>;
  return <div className="entry-list">
    {entries.map((entry) => <article className="entry-row" key={entry.id}>
      {["task", "goal", "habit", "project"].includes(entry.kind) && <form action={setEntryStatus}>
        <input type="hidden" name="id" value={entry.id} /><input type="hidden" name="status" value={entry.status} />
        <button className="entry-toggle" aria-label={entry.status === "done" ? "Reopen item" : "Mark complete"} title={entry.status === "done" ? "Reopen" : "Complete"}> </button>
      </form>}
      <div className="entry-main">
        <p className={"entry-title" + (entry.status === "done" ? " done" : "")}>{entry.title}</p>
        {entry.content && <p className="entry-detail">{entry.content}</p>}
        <div className="entry-meta"><span className="pill">{entry.kind}</span>{entry.priority === "high" && <span className="pill high">important</span>}
          {entry.due_at && <span>Due {formatDate(entry.due_at)}</span>}{!entry.due_at && entry.created_at && <span>Saved {formatDate(entry.created_at)}</span>}
        </div>
      </div>
      <div className="entry-buttons"><form action={deleteLifeEntry}><input type="hidden" name="id" value={entry.id} /><button className="icon-button" aria-label={"Delete " + entry.title}>Delete</button></form></div>
    </article>)}
  </div>;
}
