import React from 'react';
import { Tag, Folder, Image as ImageIcon, ToggleLeft, Plus, List, Pencil, Trash2, CircleCheck, CircleX } from 'lucide-react';
import api, { uploadImage } from './api';
import { errorText, fetchAll } from './uiUtils';
import SafeImage from './SafeImage';
import { compressImageToWebp } from './compressImageToWebp';

const EMPTY = { id: null, name: '', category_id: '', active: 'true', image: '' };
const PAGE_SIZE = 20;

export default function SubCategoriesPage({ canWrite }) {
  const [form, setForm] = React.useState(EMPTY);
  const [file, setFile] = React.useState(null);
  const [fileKey, setFileKey] = React.useState(0);
  const [categories, setCategories] = React.useState([]);
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
      const response = await api.get('subcategories', { params: { search, page, page_size: PAGE_SIZE } });
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
  React.useEffect(() => {
    let active = true;
    fetchAll(api, 'categories').then((rows) => { if (active) setCategories(rows); }).catch(() => { if (active) setCategories([]); });
    return () => { active = false; };
  }, []);

  function reset() { setForm(EMPTY); setFile(null); setFileKey((k) => k + 1); }

  async function submit(event) {
    event.preventDefault();
    if (saving) return;
    const name = form.name.trim();
    if (!name) { setError('Sub category name is required.'); return; }
    if (!form.category_id) { setError('Select a main category.'); return; }
    setSaving(true); setError(''); setNotice('');
    try {
      let image = form.image || null;
      if (file) image = (await uploadImage(await compressImageToWebp(file))).image_path;
      const payload = { name: name, category_id: Number(form.category_id), active: form.active === 'true', image: image };
      if (form.id) await api.patch('subcategories', Object.assign({}, payload, { id: form.id }));
      else await api.post('subcategories', payload);
      setNotice(form.id ? 'Sub category updated.' : 'Sub category saved.');
      reset();
      await load();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setSaving(false);
    }
  }

  async function remove(row) {
    if (!window.confirm('Delete sub category "' + row.name + '"? This cannot be undone.')) return;
    setError(''); setNotice('');
    try {
      await api.delete('subcategories', { params: { id: row.id } });
      setNotice('Sub category deleted.');
      if (form.id === row.id) reset();
      await load();
    } catch (err) {
      setError(errorText(err));
    }
  }

  function edit(row) {
    setForm({ id: row.id, name: row.name, category_id: String(row.category_id), active: String(Boolean(row.active)), image: row.image || '' });
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
            <label><span><Tag size={16} /> Sub Category Name</span>
              <input value={form.name} maxLength={255} placeholder="Enter subcategory name" onChange={(e) => setForm({ ...form, name: e.target.value })} required /></label>
            <label><span><Folder size={16} /> Main Category <b className="sk-req">*</b></span>
              <select value={form.category_id} onChange={(e) => setForm({ ...form, category_id: e.target.value })} required>
                <option value="">-- Select Main Category --</option>
                {categories.map((c) => <option key={c.id} value={String(c.id)}>{c.name}</option>)}
              </select>
              <small>Select the parent category that this subcategory belongs to.</small></label>
            <label><span><ImageIcon size={16} /> Sub Category Image</span>
              <input key={fileKey} type="file" accept="image/jpeg,image/png,image/gif,image/webp" onChange={(e) => setFile(e.target.files?.[0] || null)} />
              <small>JPG, PNG, GIF or WEBP. Images are automatically compressed and converted to WebP with no frontend file-size limit. Optional during edit.{currentImage}</small></label>
            <label><span><ToggleLeft size={16} /> Status</span>
              <select value={form.active} onChange={(e) => setForm({ ...form, active: e.target.value })}>
                <option value="true">Active</option>
                <option value="false">Inactive</option>
              </select>
              <small>Inactive subcategories will hide all products under this subcategory.</small></label>
          </div>
          <div className="button-row">
            <button className="sk-btn-primary" disabled={saving}><Plus size={16} /> {saving ? 'Saving...' : (form.id ? 'Update Sub Category' : 'Save Sub Category')}</button>
            {form.id && <button type="button" onClick={reset} disabled={saving}>Cancel edit</button>}
          </div>
        </form>
      )}
      {error && <p className="error" role="alert">{error}</p>}
      {notice && <p className="success" role="status">{notice}</p>}
      <div className="sk-list-head">
        <h2><List size={20} /> All Sub Categories</h2>
        <input className="sk-search" aria-label="Search sub categories" placeholder="Search sub categories" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
      </div>
      <section className="sk-card sk-flush">
        <div className="table-wrap">
          <table className="sk-table sk-upper-head">
            <thead><tr><th>Name</th><th>Main Category</th><th>Image</th><th>Status</th>{canWrite && <th className="sk-right">Actions</th>}</tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td><strong>{row.name}</strong></td>
                  <td>{row.category_name ? <span className="sk-tag">{row.category_name}</span> : '-'}</td>
                  <td><SafeImage className="sk-thumb" src={row.image_url} alt={row.name} /></td>
                  <td><span className={row.active ? 'sk-pill' : 'sk-pill sk-pill-off'}>{row.active ? <CircleCheck size={13} /> : <CircleX size={13} />} {row.active ? 'Active' : 'Inactive'}</span></td>
                  {canWrite && <td className="sk-right"><button type="button" className="sk-btn-edit" onClick={() => edit(row)}><Pencil size={14} /> Edit</button> <button type="button" className="sk-btn-delete" onClick={() => remove(row)}><Trash2 size={14} /> Delete</button></td>}
                </tr>
              ))}
              {loading && <tr><td colSpan="5" className="empty" role="status">Loading sub categories...</td></tr>}
              {!loading && !error && rows.length === 0 && <tr><td colSpan="5" className="empty">No sub categories found.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
      {data && data.count > 0 && (
        <div className="pagination">
          <span>{data.count} sub categories - Page {page} of {pages}</span>
          <div className="button-row">
            <button disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>Previous</button>
            <button disabled={page >= pages || loading} onClick={() => setPage(page + 1)}>Next</button>
          </div>
        </div>
      )}
    </div>
  );
}