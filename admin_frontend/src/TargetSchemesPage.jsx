import React from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Home, Target as TargetIcon, Plus, RefreshCw, Pencil, Trash2, Power, X, Search } from "lucide-react";
import api, { uploadImage } from "./api";
import SafeImage from "./SafeImage";
import { errorText, fetchAll, validateRewardImageFile } from "./uiUtils";
import "./TargetSchemesPage.css";

const money = (v) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(Number(v) || 0);
const EMPTY_FORM = {
  target_name: "", category_id: "", target_amount: "", reward_description: "", scheme_benefits: "",
  reward_image: "", start_date: "", end_date: "",
};
const TABS = [
  ["targets", "Targets"],
  ["achievements", "User Achievements"],
  ["top", "Top Achievers"],
  ["debug", "Debug"],
];
const isAchieved = (a) => String(a.status).toUpperCase() === "ACHIEVED" || Boolean(a.achieved_date);
const countBy = (rows, key) => rows.reduce((m, r) => ({ ...m, [r[key]]: (m[r[key]] || 0) + 1 }), {});

function validate(form) {
  const errors = {};
  if (!form.target_name.trim()) errors.target_name = "Target name is required.";
  if (!/^[1-9][0-9]*$/.test(String(form.category_id))) errors.category_id = "Select a category.";
  const amount = Number(form.target_amount);
  if (form.target_amount === "" || !Number.isFinite(amount) || amount <= 0) errors.target_amount = "Enter an amount greater than zero.";
  if (!form.reward_description.trim()) errors.reward_description = "Reward description is required.";
  if (!form.start_date) errors.start_date = "Start date is required.";
  if (!form.end_date) errors.end_date = "End date is required.";
  if (form.start_date && form.end_date && form.end_date < form.start_date) errors.end_date = "End date cannot be earlier than start date.";
  return errors;
}

export default function TargetSchemesPage({ canWrite = false }) {
  const navigate = useNavigate();
  const [targets, setTargets] = React.useState([]);
  const [categories, setCategories] = React.useState([]);
  const [users, setUsers] = React.useState([]);
  const [assignments, setAssignments] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");
  const [notice, setNotice] = React.useState("");
  const [tab, setTab] = React.useState("targets");
  const [search, setSearch] = React.useState("");
  const [modal, setModal] = React.useState(null);
  const [form, setForm] = React.useState(EMPTY_FORM);
  const [fieldErrors, setFieldErrors] = React.useState({});
  const [formError, setFormError] = React.useState("");
  const [selected, setSelected] = React.useState([]);
  const [userSearch, setUserSearch] = React.useState("");
  const [preview, setPreview] = React.useState("");
  const [uploading, setUploading] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [rowBusy, setRowBusy] = React.useState(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [t, c, u, a] = await Promise.all([
        fetchAll(api, "targets"),
        fetchAll(api, "categories"),
        fetchAll(api, "customers"),
        fetchAll(api, "targets/assignments"),
      ]);
      setTargets(t);
      setCategories(c);
      setUsers(u);
      setAssignments(a);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, []);
  // oxlint-disable-next-line react/set-state-in-effect -- intentional API-loading effect.
  React.useEffect(() => { load(); }, [load]);

  const categoryName = React.useCallback((id) => {
    const c = categories.find((x) => String(x.id ?? x.category_id) === String(id));
    return c ? c.name || c.category_name || "#" + id : "#" + id;
  }, [categories]);
  const userLabel = React.useCallback((id) => {
    const u = users.find((x) => String(x.id ?? x.user_id) === String(id));
    return u ? u.full_name || u.username || "User " + id : "User " + id;
  }, [users]);
  const assignedByTarget = React.useMemo(() => {
    const map = new Map();
    for (const a of assignments) {
      const key = String(a.target_id);
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(a);
    }
    return map;
  }, [assignments]);

  const stats = React.useMemo(() => ({
    total: targets.length,
    active: targets.filter((t) => String(t.status).toUpperCase() === "ACTIVE").length,
    achieved: assignments.filter(isAchieved).length,
    assignments: assignments.length,
  }), [targets, assignments]);

  const visibleTargets = React.useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return targets;
    return targets.filter((t) =>
      [t.target_name, t.reward_description, t.status, categoryName(t.category_id)].some((v) => String(v || "").toLowerCase().includes(q)));
  }, [targets, search, categoryName]);

  const selectableUsers = React.useMemo(
    () => users.filter((u) => String(u.status || "").toUpperCase() === "ACTIVE"), [users]);
  const alreadyAssigned = React.useMemo(() => {
    if (modal?.mode !== "edit") return new Set();
    return new Set((assignedByTarget.get(String(modal.id)) || []).map((a) => String(a.user_id)));
  }, [modal, assignedByTarget]);
  const shownUsers = selectableUsers.filter((u) => {
    const q = userSearch.trim().toLowerCase();
    return !q || [u.full_name, u.username, u.shop_name].some((v) => String(v || "").toLowerCase().includes(q));
  });

  function openCreate() {
    setForm(EMPTY_FORM); setSelected([]); setFieldErrors({}); setFormError(""); setPreview(""); setUserSearch("");
    setModal({ mode: "create" });
  }
  function openEdit(t) {
    setForm({
      target_name: t.target_name || "", category_id: String(t.category_id ?? ""), target_amount: String(t.target_amount ?? ""),
      reward_description: t.reward_description || "", scheme_benefits: t.scheme_benefits || "",
      reward_image: t.reward_image || "", start_date: t.start_date || "", end_date: t.end_date || "",
    });
    setSelected([]); setFieldErrors({}); setFormError(""); setUserSearch("");
    setPreview(t.reward_image_url || "");
    setModal({ mode: "edit", id: t.id });
  }
  function closeModal() {
    if (saving) return;
    if (preview.startsWith("blob:")) URL.revokeObjectURL(preview);
    setModal(null);
  }
  const setField = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  async function pickImage(e) {
    const file = e.target.files && e.target.files[0];
    e.target.value = "";
    if (!file) return;
    const problem = validateRewardImageFile(file);
    if (problem) { setFieldErrors((x) => ({ ...x, reward_image: problem })); return; }
    setUploading(true);
    setFieldErrors((x) => ({ ...x, reward_image: "" }));
    try {
      const data = await uploadImage(file);
      setForm((f) => ({ ...f, reward_image: data.image_path }));
      setPreview((old) => {
        if (old.startsWith("blob:")) URL.revokeObjectURL(old);
        return URL.createObjectURL(file);
      });
    } catch (err) {
      setFieldErrors((x) => ({ ...x, reward_image: (err.response && err.response.data && err.response.data.file) || errorText(err) }));
    } finally {
      setUploading(false);
    }
  }

  const toggleUser = (id) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const selectAll = () =>
    setSelected(shownUsers.map((u) => String(u.id)).filter((id) => !alreadyAssigned.has(id)));

  async function submit(e) {
    e.preventDefault();
    if (saving || uploading) return;
    const errors = validate(form);
    setFieldErrors(errors);
    setFormError("");
    if (Object.keys(errors).length) return;
    setSaving(true);
    const payload = {
      target_name: form.target_name.trim(), category_id: Number(form.category_id), target_amount: String(form.target_amount),
      reward_description: form.reward_description.trim(), scheme_benefits: form.scheme_benefits.trim(),
      reward_image: form.reward_image, start_date: form.start_date, end_date: form.end_date,
    };
    let targetId = modal.id;
    const mode = modal.mode;
    try {
      if (mode === "create") {
        const res = await api.post("targets", { ...payload, status: "ACTIVE" });
        targetId = res.data.id;
      } else {
        await api.patch("targets", { id: modal.id, ...payload });
      }
    } catch (err) {
      const data = err.response && err.response.data;
      if (data && typeof data === "object" && err.response.status === 400) {
        const mapped = {};
        for (const k of Object.keys(EMPTY_FORM)) if (data[k]) mapped[k] = String(data[k]);
        setFieldErrors(mapped);
      }
      setFormError(errorText(err));
      setSaving(false);
      return;
    }
    const toAssign = selected.filter((id) => !alreadyAssigned.has(id));
    const failed = [];
    let created = 0;
    let duplicates = 0;
    for (const userId of toAssign) {
      try {
        await api.post("targets/assignments", { target_id: targetId, user_id: Number(userId) });
        created += 1;
      } catch (err) {
        if (err.response && err.response.status === 409) duplicates += 1;
        else failed.push(userLabel(userId) + ": " + errorText(err));
      }
    }
    await load();
    setSaving(false);
    if (failed.length) {
      setModal({ mode: "edit", id: targetId });
      setSelected([]);
      setFormError("Target saved, but " + failed.length + " of " + toAssign.length + " assignment(s) failed: " + failed.join("; "));
      return;
    }
    if (preview.startsWith("blob:")) URL.revokeObjectURL(preview);
    setModal(null);
    let message = "Target " + (mode === "create" ? "created" : "updated") + ".";
    if (toAssign.length) message += " " + created + " user(s) assigned" + (duplicates ? ", " + duplicates + " already assigned" : "") + ".";
    setNotice(message);
  }

  async function toggleStatus(t) {
    if (rowBusy) return;
    const next = String(t.status).toUpperCase() === "ACTIVE" ? "INACTIVE" : "ACTIVE";
    setRowBusy(t.id); setError(""); setNotice("");
    try {
      await api.patch("targets", { id: t.id, status: next });
      setNotice("Target " + (next === "ACTIVE" ? "activated" : "deactivated") + ".");
      await load();
    } catch (err) { setError(errorText(err)); } finally { setRowBusy(null); }
  }
  async function remove(t) {
    if (rowBusy || !window.confirm('Delete target "' + t.target_name + '"?')) return;
    setRowBusy(t.id); setError(""); setNotice("");
    try {
      await api.delete("targets", { params: { id: t.id } });
      setNotice("Target deleted.");
      await load();
    } catch (err) { setError(errorText(err)); } finally { setRowBusy(null); }
  }

  const topAchievers = React.useMemo(() => {
    const byUser = new Map();
    for (const a of assignments) {
      const amount = Number(a.achieved_amount) || 0;
      if (amount <= 0) continue;
      const row = byUser.get(String(a.user_id)) || { user_id: a.user_id, amount: 0, orders: 0, targets: 0 };
      row.amount += amount; row.orders += Number(a.order_count) || 0; row.targets += 1;
      byUser.set(String(a.user_id), row);
    }
    return [...byUser.values()].sort((x, y) => y.amount - x.amount);
  }, [assignments]);

  const targetName = (id) => {
    const t = targets.find((x) => String(x.id) === String(id));
    return t ? t.target_name : "Target #" + id;
  };


  return (
    <div className="tsp">
      <header className="tsp-header">
        <button type="button" className="tsp-back" onClick={() => navigate(-1)}><ArrowLeft size={18} /> Back</button>
        <h1>Target Management</h1>
        <span className="tsp-home"><Home size={16} /> Home</span>
      </header>

      <div className="tsp-body">
        <div className="tsp-titlebar">
          <h2><TargetIcon size={26} /> Target Management</h2>
          {canWrite && <button type="button" className="tsp-btn tsp-primary" onClick={openCreate}><Plus size={18} /> Create New Target</button>}
        </div>

        {notice && <div className="tsp-alert tsp-ok" role="status">{notice}</div>}
        {error && <div className="tsp-alert tsp-bad" role="alert">{error}</div>}

        <section className="tsp-stats" aria-label="Target statistics">
          {[["Total Targets", stats.total], ["Active Targets", stats.active], ["Achieved Targets", stats.achieved], ["Total Assignments", stats.assignments]].map(([label, value]) => (
            <div className="tsp-card tsp-stat" key={label}><strong>{value}</strong><span>{label}</span></div>
          ))}
        </section>

        <nav className="tsp-tabs" role="tablist">
          {TABS.map(([key, label]) => (
            <button key={key} type="button" role="tab" aria-selected={tab === key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}>{label}</button>
          ))}
        </nav>

        <section className="tsp-card tsp-panel">
          {tab === "targets" && (
            <>
              <div className="tsp-toolbar">
                <h3>All Targets</h3>
                <div className="tsp-tools">
                  <label className="tsp-search"><Search size={16} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search targets" aria-label="Search targets" /></label>
                  <button type="button" className="tsp-btn" onClick={load} disabled={loading}><RefreshCw size={16} /> Refresh</button>
                </div>
              </div>
              <div className="tsp-scroll">
                <table className="tsp-table">
                  <thead><tr>
                    <th>#</th><th>Target Name</th><th>Category</th><th>Target Amount</th><th>Reward</th><th>Scheme Benefits</th>
                    <th>Period</th><th>Assigned Users</th><th>Achieved</th><th>Status</th><th>Actions</th>
                  </tr></thead>
                  <tbody>
                    {loading && <tr><td colSpan={11} className="tsp-empty">Loading targets...</td></tr>}
                    {!loading && visibleTargets.length === 0 && <tr><td colSpan={11} className="tsp-empty">No targets found.</td></tr>}
                    {!loading && visibleTargets.map((t, i) => {
                      const rows = assignedByTarget.get(String(t.id)) || [];
                      const achieved = rows.filter(isAchieved).length;
                      const active = String(t.status).toUpperCase() === "ACTIVE";
                      return (
                        <tr key={t.id}>
                          <td>{i + 1}</td>
                          <td><strong>{t.target_name}</strong></td>
                          <td>{categoryName(t.category_id)}</td>
                          <td>{money(t.target_amount)}</td>
                          <td className="tsp-reward">
                            {t.reward_image_url && <SafeImage src={t.reward_image_url} alt="" fallback="" />}
                            <span>{t.reward_description}</span>
                          </td>
                          <td>{t.scheme_benefits || "-"}</td>
                          <td>{t.start_date} to {t.end_date}</td>
                          <td>{rows.length ? rows.map((r) => userLabel(r.user_id)).join(", ") : "None"}</td>
                          <td>{rows.length ? achieved + " of " + rows.length : "-"}</td>
                          <td><span className={"tsp-badge " + (active ? "on" : "off")}>{t.status}</span></td>
                          <td className="tsp-actions">
                            {canWrite ? (
                              <>
                                <button type="button" title="Edit" aria-label={"Edit " + t.target_name} onClick={() => openEdit(t)} disabled={rowBusy === t.id}><Pencil size={16} /></button>
                                <button type="button" title={active ? "Deactivate" : "Activate"} aria-label={(active ? "Deactivate " : "Activate ") + t.target_name} onClick={() => toggleStatus(t)} disabled={rowBusy === t.id}><Power size={16} /></button>
                                <button type="button" title="Delete" aria-label={"Delete " + t.target_name} className="danger" onClick={() => remove(t)} disabled={rowBusy === t.id}><Trash2 size={16} /></button>
                              </>
                            ) : "-"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {tab === "achievements" && (
            <>
              <h3>User Achievements</h3>
              <p className="tsp-note">Showing assignment progress from the assignments endpoint. A dedicated achievement-history reporting API is not yet implemented.</p>
              <div className="tsp-scroll">
                <table className="tsp-table">
                  <thead><tr><th>User</th><th>Target</th><th>Achieved Amount</th><th>Orders</th><th>Status</th><th>Achieved Date</th></tr></thead>
                  <tbody>
                    {assignments.length === 0 && <tr><td colSpan={6} className="tsp-empty">No assignments yet.</td></tr>}
                    {assignments.map((a) => (
                      <tr key={a.assignment_id}>
                        <td>{userLabel(a.user_id)}</td><td>{targetName(a.target_id)}</td><td>{money(a.achieved_amount)}</td>
                        <td>{a.order_count}</td><td>{a.status}</td><td>{a.achieved_date || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {tab === "top" && (
            <>
              <h3>Top Achievers</h3>
              <p className="tsp-note">Ranked by total achieved amount recorded on real assignments. Users with no recorded achievement are not listed.</p>
              <div className="tsp-scroll">
                <table className="tsp-table">
                  <thead><tr><th>Rank</th><th>User</th><th>Total Achieved</th><th>Orders</th><th>Targets</th></tr></thead>
                  <tbody>
                    {topAchievers.length === 0 && <tr><td colSpan={5} className="tsp-empty">No achievements recorded yet.</td></tr>}
                    {topAchievers.map((r, i) => (
                      <tr key={r.user_id}><td>{i + 1}</td><td>{userLabel(r.user_id)}</td><td>{money(r.amount)}</td><td>{r.orders}</td><td>{r.targets}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {tab === "debug" && (
            <>
              <h3>Debug</h3>
              <dl className="tsp-debug">
                <dt>Targets loaded</dt><dd>{targets.length}</dd>
                <dt>Assignments loaded</dt><dd>{assignments.length}</dd>
                <dt>Categories loaded</dt><dd>{categories.length}</dd>
                <dt>Users loaded</dt><dd>{users.length} ({selectableUsers.length} active)</dd>
                <dt>Target statuses</dt><dd>{JSON.stringify(countBy(targets, "status"))}</dd>
                <dt>Assignment statuses</dt><dd>{JSON.stringify(countBy(assignments, "status"))}</dd>
                <dt>Assignments with unknown target</dt><dd>{assignments.filter((a) => !targets.some((t) => t.id === a.target_id)).length}</dd>
                <dt>Targets with unknown category</dt><dd>{targets.filter((t) => !categories.some((c) => String(c.id ?? c.category_id) === String(t.category_id))).length}</dd>
                <dt>Target fields</dt><dd>{targets[0] ? Object.keys(targets[0]).join(", ") : "-"}</dd>
                <dt>Assignment fields</dt><dd>{assignments[0] ? Object.keys(assignments[0]).join(", ") : "-"}</dd>
              </dl>
            </>
          )}
        </section>
      </div>

      {modal && (
        <div className="tsp-overlay" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) closeModal(); }}>
          <form className="tsp-modal" role="dialog" aria-modal="true" aria-labelledby="tsp-modal-title" onSubmit={submit} noValidate>
            <div className="tsp-modal-head">
              <h2 id="tsp-modal-title">{modal.mode === "create" ? "Create New Target" : "Edit Target"}</h2>
              <button type="button" onClick={closeModal} aria-label="Close" disabled={saving}><X size={20} /></button>
            </div>
            <div className="tsp-modal-body">
              {formError && <div className="tsp-alert tsp-bad" role="alert">{formError}</div>}
              <label>Target Name *<input value={form.target_name} onChange={setField("target_name")} maxLength={255} />{fieldErrors.target_name && <em>{fieldErrors.target_name}</em>}</label>
              <label>Category *
                <select value={form.category_id} onChange={setField("category_id")}>
                  <option value="">Select category</option>
                  {categories.map((c) => <option key={c.id ?? c.category_id} value={String(c.id ?? c.category_id)}>{c.name || c.category_name}</option>)}
                </select>
                {fieldErrors.category_id && <em>{fieldErrors.category_id}</em>}
              </label>
              <label>Target Amount (Rs.) *<input type="number" min="0" step="0.01" value={form.target_amount} onChange={setField("target_amount")} />{fieldErrors.target_amount && <em>{fieldErrors.target_amount}</em>}</label>
              <label>Reward Description *<input value={form.reward_description} onChange={setField("reward_description")} />{fieldErrors.reward_description && <em>{fieldErrors.reward_description}</em>}</label>
              <label>Scheme Benefits<textarea rows={3} value={form.scheme_benefits} onChange={setField("scheme_benefits")} /></label>
              <label>Reward Image
                <input type="file" accept="image/jpeg,image/png,image/gif,image/webp" onChange={pickImage} disabled={uploading || saving} />
                <small>JPG, PNG, GIF or WebP, up to 5 MB.{uploading ? " Uploading..." : ""}</small>
                {preview && <SafeImage className="tsp-preview" src={preview} alt="Reward preview" fallback="Preview unavailable" />}
                {form.reward_image && <small>Saved path: {form.reward_image}</small>}
                {fieldErrors.reward_image && <em>{fieldErrors.reward_image}</em>}
              </label>
              <div className="tsp-dates">
                <label>Start Date *<input type="date" value={form.start_date} onChange={setField("start_date")} />{fieldErrors.start_date && <em>{fieldErrors.start_date}</em>}</label>
                <label>End Date *<input type="date" value={form.end_date} min={form.start_date || undefined} onChange={setField("end_date")} />{fieldErrors.end_date && <em>{fieldErrors.end_date}</em>}</label>
              </div>
              <fieldset className="tsp-users">
                <legend>Assign to Users</legend>
                <div className="tsp-user-tools">
                  <input value={userSearch} onChange={(e) => setUserSearch(e.target.value)} placeholder="Search users" aria-label="Search users" />
                  <button type="button" className="tsp-btn" onClick={selectAll}>Select All</button>
                  <button type="button" className="tsp-btn" onClick={() => setSelected([])}>Deselect All</button>
                </div>
                <div className="tsp-user-list">
                  {shownUsers.length === 0 && <p className="tsp-empty">No active users found.</p>}
                  {shownUsers.map((u) => {
                    const id = String(u.id);
                    const had = alreadyAssigned.has(id);
                    return (
                      <label key={id} className="tsp-check">
                        <input type="checkbox" checked={had || selected.includes(id)} disabled={had} onChange={() => toggleUser(id)} />
                        <span>{u.full_name || u.username}{u.shop_name ? " - " + u.shop_name : ""}{had ? " (already assigned)" : ""}</span>
                      </label>
                    );
                  })}
                </div>
                <small>{selected.length} new user(s) selected. Existing assignments are never removed here.</small>
              </fieldset>
            </div>
            <div className="tsp-modal-foot">
              <button type="button" className="tsp-btn" onClick={closeModal} disabled={saving}>Cancel</button>
              <button type="submit" className="tsp-btn tsp-primary" disabled={saving || uploading}>{saving ? "Saving..." : modal.mode === "create" ? "Create Target" : "Save Changes"}</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
