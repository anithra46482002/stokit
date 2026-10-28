import React from 'react';
import { Tag, Image as ImageIcon, ToggleLeft, Plus, List, Pencil, Trash2, CircleCheck, CircleX } from 'lucide-react';
import api, { uploadImage } from './api';
import SafeImage from './SafeImage';

const EMPTY = { id: null, name: '', active: 'true', image: '' };
const PAGE_SIZE = 20;

function errorText(err) {
  const data = err.response?.data;
  if (!data) return err.message || 'Request failed';
  if (typeof data === 'string') return data;
  return data.detail || data.message || Object.values(data).filter((v) => typeof v === 'string').join(' ') || 'Request failed';
}

export default function CategoriesPage({ canWrite }) {
  const [form, setForm] = React.useState(EMPTY);
  const [file, setFile] = React.useState(null);
  const [fileKey, setFileKey] = React.useState(0);
  const [data, setData] = React.useState(null);
  const [search, setSearch] = React.useState('');
  const [page, setPage] = React.useState(1);
  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState('');
  const [notice, setNotice] = React.useState('');

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get('categories', { params: { search, page, page_size: PAGE_SIZE } });
      setData(response.data);
      setError('');
    } catch (err) {
      setData(null);
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }, [search, page]);
  // oxlint-disable-next-line react/set-state-in-effect
  React.useEffect(() => { load(); }, [load]);

  function reset() { setForm(EMPTY); setFile(null); setFileKey((k) => k + 1); }

  async function submit(event) {
    event.preventDefault();
    if (saving) return;
    const name = form.name.trim();
    if (!name) { setError('Category name is required.'); return; }
    setSaving(true); setError(''); setNotice('');
    try {
      let image = form.image || null;
      if (file) image = (await uploadImage(file)).image_path;
      const payload = { name: name, active: form.active === 'true', image: image };
      if (form.id) await api.patch('categories', Object.assign({}, payload, { id: form.id }));
      else await api.post('categories', payload);
      setNotice(form.id ? 'Category updated.' : 'Category saved.');
      reset();
      await load();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setSaving(false);
    }
  }

  async function remove(row) {
    if (!window.confirm('Delete category "' + row.name + '"? This cannot be undone.')) return;
    setError(''); setNotice('');
    try {
      await api.delete('categories', { params: { id: row.id } });
      setNotice('Category deleted.');
      if (form.id === row.id) reset();
      await load();
    } catch (err) {
      setError(errorText(err));
    }
  }

  function edit(row) {
    setForm({ id: row.id, name: row.name, active: String(Boolean(row.active)), image: row.image || '' });
    setFile(null); setFileKey((k) => k + 1); setNotice(''); setError('');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  const rows = data?.results || [];
  const pages = Math.max(1, Math.ceil((data?.count || 0) / PAGE_SIZE));
  const currentImage = form.image && !file ? ' Current: ' + form.image : '';
  return (
    <div className="sk-page">
      {canWrite && (
        <form className="sk-card sk-form" onSubmit={submit}>
          <div className="sk-form-grid">
            <label><span><Tag size={16} /> Category Name</span>
              <input value={form.name} maxLength={255} placeholder="Enter category name" onChange={(e) => setForm({ ...form, name: e.target.value })} required /></label>
            <label><span><ImageIcon size={16} /> Category Image</span>
              <input key={fileKey} type="file" accept="image/jpeg,image/png,image/gif,image/webp" onChange={(e) => setFile(e.target.files?.[0] || null)} />
              <small>JPG, PNG, GIF or WEBP up to 5 MB. Optional during edit.{currentImage}</small></label>
            <label><span><ToggleLeft size={16} /> Status</span>
              <select value={form.active} onChange={(e) => setForm({ ...form, active: e.target.value })}>
                <option value="true">Active</option>
                <option value="false">Inactive</option>
              </select>
              <small>Inactive categories will hide all products under this category.</small></label>
          </div>
          <div className="button-row">
            <button className="sk-btn-primary" disabled={saving}><Plus size={16} /> {saving ? 'Saving...' : (form.id ? 'Update Category' : 'Save Category')}</button>
            {form.id && <button type="button" onClick={reset} disabled={saving}>Cancel edit</button>}
          </div>
        </form>
      )}
      {error && <p className="error" role="alert">{error}</p>}
      {notice && <p className="success" role="status">{notice}</p>}
      <div className="sk-list-head">
        <h2><List size={20} /> All Categories</h2>
        <input className="sk-search" aria-label="Search categories" placeholder="Search categories" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
      </div>
      <section className="sk-card sk-flush">
        <div className="table-wrap">
          <table className="sk-table sk-upper-head">
            <thead><tr><th>Name</th><th>Image</th><th>Status</th>{canWrite && <th className="sk-right">Actions</th>}</tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td><strong>{row.name}</strong></td>
                  <td><SafeImage className="sk-thumb" src={row.image_url} alt={row.name} /></td>
                  <td><span className={row.active ? 'sk-pill' : 'sk-pill sk-pill-off'}>{row.active ? <CircleCheck size={13} /> : <CircleX size={13} />} {row.active ? 'Active' : 'Inactive'}</span></td>
                  {canWrite && <td className="sk-right"><button type="button" className="sk-btn-edit" onClick={() => edit(row)}><Pencil size={14} /> Edit</button> <button type="button" className="sk-btn-delete" onClick={() => remove(row)}><Trash2 size={14} /> Delete</button></td>}
                </tr>
              ))}
              {loading && <tr><td colSpan="4" className="empty" role="status">Loading categories...</td></tr>}
              {!loading && !error && rows.length === 0 && <tr><td colSpan="4" className="empty">No categories found.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
      {data && data.count > 0 && (
        <div className="pagination">
          <span>{data.count} categories - Page {page} of {pages}</span>
          <div className="button-row">
            <button disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>Previous</button>
            <button disabled={page >= pages || loading} onClick={() => setPage(page + 1)}>Next</button>
          </div>
        </div>
      )}
    </div>
  );
}