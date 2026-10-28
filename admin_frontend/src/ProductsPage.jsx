import React from 'react';
import { Search, Plus, Pencil, Trash2, Warehouse } from 'lucide-react';
import api, { uploadImage } from './api';
import CrudDialog from './CrudDialog';
import SafeImage from './SafeImage';
import {
  MINIMUM_BUYING_QUANTITY_DEFAULT,
  MINIMUM_BUYING_QUANTITY_FIELD,
  PRODUCT_SETTING_FIELDS,
  minimumBuyingQuantityFormValue,
  validateMinimumBuyingQuantity,
} from './productSettings';
import { errorText, fetchAll } from './uiUtils';
import { buildProductPayload, describeProductDeleteError, newSaveProgress, saveProductForm } from './productFormActions';
import { deleteRecord, pageAfterDelete } from './variantActions';
import { compressImageToWebp } from './compressImageToWebp';

const PAGE_SIZE = 20;
const BLANK = { name: '', code: '', stock: '', price: '', mrp: '', discount: '', no_discount_banner: 'N', disable_variants: 'N', minimum_buying_count: MINIMUM_BUYING_QUANTITY_DEFAULT, gst_applicable: 'N', gst_percentage: '0', gst_price: '0', description: '', keywords: '', subtitle: '', brand: '', set_contains: '[]', discount_banners: [], category_id: '', subcategory_id: '', visible: '1', highlight: false };

export default function ProductsPage({ canWrite }) {
  const [data, setData] = React.useState(null);
  const [searchText, setSearchText] = React.useState('');
  const [search, setSearch] = React.useState('');
  const [visible, setVisible] = React.useState('');
  const [warehouse, setWarehouse] = React.useState('');
  const [warehouses, setWarehouses] = React.useState([]);
  const [categories, setCategories] = React.useState([]);
  const [subcategories, setSubcategories] = React.useState([]);
  const [page, setPage] = React.useState(1);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const [editing, setEditing] = React.useState(null);
  const [productImageFiles, setProductImageFiles] = React.useState([]);
  const [bannerFiles, setBannerFiles] = React.useState([]);
  const [removedBannerPaths, setRemovedBannerPaths] = React.useState([]);
  const [error, setError] = React.useState('');
  const [notice, setNotice] = React.useState('');
  const saveProgress = React.useRef(newSaveProgress());
  const originals = React.useRef({});

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const params = { search, page, page_size: PAGE_SIZE };
      if (visible) params.visible = visible;
      if (warehouse) params.warehouse_id = warehouse;
      const response = await api.get('products', { params });
      setData(response.data);
      setError('');
    } catch (err) {
      setData(null);
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }, [search, page, visible, warehouse]);
  // oxlint-disable-next-line react/set-state-in-effect
  React.useEffect(() => { load(); }, [load]);

  React.useEffect(() => {
    let active = true;
    fetchAll(api, 'categories').then((rows) => { if (active) setCategories(rows); }).catch(() => {});
    // Warehouse list needs the warehouse permission; the filter simply stays empty without it.
    fetchAll(api, 'warehouses').then((rows) => { if (active) setWarehouses(rows); }).catch(() => {});
    return () => { active = false; };
  }, []);

  const editCategory = editing?.category_id;
  React.useEffect(() => {
    let active = true;
    if (!editCategory) return () => { active = false; };
    fetchAll(api, 'subcategories', { category_id: editCategory }).then((rows) => { if (active) setSubcategories(rows); }).catch(() => { if (active) setSubcategories([]); });
    return () => { active = false; };
  }, [editCategory]);

  function runSearch(event) { event.preventDefault(); setPage(1); setSearch(searchText.trim()); }

  async function toggleVisible(row) {
    if (busy) return;
    setBusy(true); setError(''); setNotice('');
    try {
      await api.patch('products', { id: row.id, visible: row.visible === '1' ? '0' : '1' });
      await load();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function hideProduct(row) {
    await api.patch('products', { id: row.id, visible: '0' });
    setNotice('Product "' + row.name + '" was hidden (archived). Its order history is preserved.');
    await load();
  }

  async function remove(row) {
    if (busy || !window.confirm('Delete product "' + row.name + '"? This cannot be undone.')) return;
    setBusy(true); setError(''); setNotice('');
    let offerHide = false;
    try {
      await deleteRecord(api, 'products', null, row.id);
      setNotice('Product deleted.');
      const nextPage = pageAfterDelete(page, rows.length);
      if (nextPage !== page) setPage(nextPage); else await load();
    } catch (err) {
      const outcome = describeProductDeleteError(err, row.name + ' (product ID ' + row.id + ')');
      if (outcome.gone) await load();
      setError(outcome.message);
      offerHide = outcome.archivable && row.visible === '1';
    } finally {
      setBusy(false);
    }
    // Protected product (order history, carts, stock history): offer the existing visibility-based archive.
    if (offerHide && window.confirm('"' + row.name + '" cannot be deleted because other records reference it. Hide it from customers instead? (Nothing is deleted; you can make it visible again later.)')) {
      setBusy(true);
      try { await hideProduct(row); setError(''); } catch (err) { setError('"' + row.name + '" could not be hidden: ' + errorText(err)); } finally { setBusy(false); }
    }
  }

  function resetEditorState() {
    saveProgress.current = newSaveProgress();
    setProductImageFiles([]); setBannerFiles([]); setRemovedBannerPaths([]);
  }

  function openForm(row) {
    setError(''); setNotice('');
    resetEditorState();
    if (!row) { originals.current = {}; setEditing(Object.assign({}, BLANK, { discount_banners: [] })); return; }
    setEditing({ id: row.id, name: row.name, code: row.code, price: row.price, mrp: row.mrp, discount: row.discount, no_discount_banner: row.no_discount_banner === 'Y' ? 'Y' : 'N', disable_variants: row.disable_variants === 'Y' ? 'Y' : 'N', minimum_buying_count: minimumBuyingQuantityFormValue(row), category_id: String(row.category_id || ''), subcategory_id: String(row.subcategory_id || ''), visible: row.visible === '1' ? '1' : '0', highlight: Boolean(row.highlight), stock: row.stock || '', gst_applicable: row.gst_applicable || 'N', gst_percentage: row.gst_percentage || '0', gst_price: row.gst_price || '0', description: row.description || '', keywords: row.keywords || '', subtitle: row.subtitle || '', brand: row.brand || '', set_contains: JSON.stringify(row.set_contains ?? [], null, 2), discount_banners: Array.isArray(row.discount_banners) ? row.discount_banners : [], image_url: row.image_url || '' });
  }

  async function save(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setError(''); setNotice('');
    // Front-end validation (the backend validates everything again); the dialog stays open on any failure.
    const built = buildProductPayload(editing);
    if (built.error) { setError(built.error); setBusy(false); return; }
    const wasNew = !editing.id;
    const progress = saveProgress.current;
    try {
      await saveProductForm(api, async (file) => uploadImage(await compressImageToWebp(file)), { values: built.values, bannerFiles, removedBannerPaths, oldBannerPaths: Array.isArray(editing.discount_banners) ? editing.discount_banners : [], productImageFiles, progress });
      setEditing(null);
      resetEditorState();
      setNotice('Product saved.');
      await load();
    } catch (err) {
      const message = err?.response ? errorText(err) : (err?.message || 'The server could not be reached');
      if (progress.productId) {
        // Part of the save is already stored: keep the dialog consistent with the database and refresh the list.
        setEditing((old) => (old && !old.id ? { ...old, id: progress.productId } : old));
        await load();
      }
      setError(message);
    } finally {
      setBusy(false);
    }
  }

  const categoryOptions = [['', '-- Select category --']].concat(categories.map((c) => [String(c.id), c.name]));
  const subOptions = [['', 'None']].concat((editCategory ? subcategories : []).map((s) => [String(s.id), s.name]));
  const fields = [
    { key: 'name', label: 'Product Name', type: 'text', required: true },
    { key: 'code', label: 'Code', type: 'text' },
    { key: 'stock', label: 'Stock Status', required: true, options: [['', '-- Select Stock Status --'], ['In Stock', 'In Stock'], ['Out of Stock', 'Out of Stock']] },
    { key: 'price', label: 'Price', type: 'number', required: true },
    { key: 'gst_applicable', label: 'GST Applicable', options: [['N', 'No'], ['Y', 'Yes']] },
    ...PRODUCT_SETTING_FIELDS,
    { key: 'description', label: 'Description', type: 'textarea' },
    { key: 'keywords', label: 'Product Keywords', type: 'textarea', help: 'Separate keywords with commas' },
    { key: 'subtitle', label: 'Subtitle', type: 'text' },
    { key: 'brand', label: 'Brand', type: 'text' },
    { key: 'discount_banners', label: 'Discount Banners (Max 10)', type: 'banner-files', existingImages: editing?.discount_banners || [], selectedFiles: bannerFiles, removedPaths: removedBannerPaths },
    { key: 'set_contains', label: 'Set contains', type: 'set-contains', help: 'Add each item included in this set product.' },
    { key: 'category_id', label: 'Category', required: true, options: categoryOptions },
    { key: 'product_image_upload', label: 'Images (Max 5)', type: 'file', accept: 'image/jpeg,image/png,image/gif,image/webp', currentImageUrl: editing?.image_url || '', multiple: true },
    { key: 'highlight', label: 'Highlight product', type: 'checkbox' },
  ];
  const editOnlyFields = [
    { key: 'mrp', label: 'MRP', type: 'number' },
    { key: 'discount', label: 'Discount', type: 'number' },
    { key: 'subcategory_id', label: 'Subcategory', options: subOptions },
    { key: 'visible', label: 'Visibility', options: [['1', 'Visible'], ['0', 'Hidden']] },
  ];
  const orderedFields = editing?.id ? [...fields.slice(0, 8), ...editOnlyFields.slice(0, 3), ...fields.slice(8, 10), ...editOnlyFields.slice(3), ...fields.slice(10)] : fields;
  // Minimum Purchase Quantity sits right after the product-level Yes/No settings, in both Add and Edit.
  const quantityField = { ...MINIMUM_BUYING_QUANTITY_FIELD, label: "Minimum Purchase Quantity", error: validateMinimumBuyingQuantity(editing?.minimum_buying_count).error || '' };
  const settingsEnd = orderedFields.findIndex((field) => field.key === 'disable_variants') + 1;
  const formFields = [...orderedFields.slice(0, settingsEnd), quantityField, ...orderedFields.slice(settingsEnd)];

  const rows = data?.results || [];
  const pages = Math.max(1, Math.ceil((data?.count || 0) / PAGE_SIZE));
  return (
    <div className="sk-page">
      {canWrite && <div className="sk-actions-top"><button className="sk-btn-primary" onClick={() => openForm(null)}><Plus size={16} /> Add Product</button></div>}
      <form className="sk-card sk-form" onSubmit={runSearch}>
        <label><span><Search size={16} /> Search Products</span>
          <div className="sk-search-row">
            <input value={searchText} placeholder="Search by product name or code..." onChange={(e) => setSearchText(e.target.value)} />
            <button className="sk-btn-primary" aria-label="Search"><Search size={16} /></button>
          </div>
        </label>
        <h3>Filters</h3>
        <div className="sk-filters">
          <label><span>Visibility</span>
            <select value={visible} onChange={(e) => { setVisible(e.target.value); setPage(1); }}>
              <option value="">All</option><option value="1">Visible</option><option value="0">Hidden</option></select></label>
          <label><span><Warehouse size={16} /> Warehouse</span>
            <select value={warehouse} onChange={(e) => { setWarehouse(e.target.value); setPage(1); }}>
              <option value="">All Warehouses</option>
              {warehouses.map((w) => <option key={w.id} value={String(w.id)}>{w.name}</option>)}</select></label>
        </div>
      </form>
      {error && <p className="error" role="alert">{error}</p>}
      {notice && <p className="success" role="status">{notice}</p>}
      <section className="sk-card sk-flush">
        <div className="table-wrap">
          <table className="sk-table sk-upper-head">
            <thead><tr><th>Name</th><th>Code</th><th>Category</th><th>Image</th><th>Visibility</th><th>Discount Y/N</th><th>Disable Variants Y/N</th>{canWrite && <th>Actions</th>}</tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td><strong>{String(row.name).toUpperCase()}</strong></td>
                  <td><span className="sk-code">{row.code}</span></td>
                  <td>{String(row.category_name || '').toUpperCase()}</td>
                  <td><SafeImage className="sk-thumb" src={row.image_url} alt={row.name} /></td>
                  <td>
                    <span className={row.visible === '1' ? 'sk-pill' : 'sk-pill sk-pill-off'}>{row.visible === '1' ? 'Visible' : 'Hidden'}</span>
                    {canWrite && <button type="button" role="switch" aria-checked={row.visible === '1'} aria-label={'Toggle visibility of ' + row.name} className={row.visible === '1' ? 'sk-switch sk-switch-on' : 'sk-switch'} onClick={() => toggleVisible(row)} disabled={busy} />}
                  </td>
                  <td><span className={row.no_discount_banner === 'Y' ? 'sk-pill' : 'sk-pill sk-pill-off'}>{row.no_discount_banner === 'Y' ? 'Yes' : 'No'}</span></td>
                  <td><span className={row.disable_variants === 'Y' ? 'sk-pill' : 'sk-pill sk-pill-off'}>{row.disable_variants === 'Y' ? 'Yes' : 'No'}</span></td>
                  {canWrite && <td><button type="button" className="sk-btn-edit sk-icon-btn" aria-label={'Edit ' + row.name} onClick={() => openForm(row)}><Pencil size={15} /></button> <button type="button" className="sk-btn-delete sk-icon-btn" aria-label={'Delete ' + row.name} onClick={() => remove(row)} disabled={busy}><Trash2 size={15} /></button></td>}
                </tr>
              ))}
              {loading && <tr><td colSpan={canWrite ? 7 : 6} className="empty" role="status">Loading products...</td></tr>}
              {!loading && !error && rows.length === 0 && <tr><td colSpan={canWrite ? 7 : 6} className="empty">No products found.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
      {data && data.count > 0 && (
        <div className="pagination">
          <span>{data.count} products - Page {page} of {pages}</span>
          <div className="button-row">
            <button disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>Previous</button>
            <button disabled={page >= pages || loading} onClick={() => setPage(page + 1)}>Next</button>
          </div>
        </div>
      )}
      {editing && <CrudDialog title={editing.id ? 'Edit product' : 'Add product'} fields={formFields} value={editing} busy={busy} error={error} onClose={() => { setEditing(null); resetEditorState(); }} onChange={(key, value) => { if (key === 'discount_banners') { const files = Array.from(value || []); const allowed = ['image/jpeg','image/png','image/gif','image/webp']; const invalid = files.find((file) => file.size > 5 * 1024 * 1024 || !allowed.includes(file.type)); const existingCount = (editing.discount_banners || []).filter((path) => !removedBannerPaths.includes(path)).length; if (existingCount + bannerFiles.length + files.length > 10) { setError('A product can have at most 10 discount banners.'); return; } if (invalid) { setError('Each banner must be a JPG, JPEG, PNG, GIF or WEBP image.'); return; } setBannerFiles((old) => [...old, ...files]); setError(''); return; } if (key === 'remove_discount_banner') { setRemovedBannerPaths((old) => old.includes(value) ? old : [...old, value]); setEditing((old) => ({ ...old, discount_banners: (old.discount_banners || []).filter((path) => path !== value) })); return; } if (key === 'remove_selected_discount_banner') { setBannerFiles((old) => old.filter((_, index) => index !== value)); return; } if (key === 'product_image_upload') { const files = Array.from(value || []); if (files.length > 5) { setError('Select no more than 5 product images.'); return; } const invalid = files.find((file) => !['image/jpeg','image/png','image/gif','image/webp'].includes(file.type)); if (invalid) { setError('Each image must be JPG, PNG, GIF or WEBP. Images are automatically converted to WebP.'); return; } setProductImageFiles(files); setError(''); return; } setEditing((prev) => Object.assign({}, prev, { [key]: value }, key === 'category_id' ? { subcategory_id: '' } : {})); }} onSubmit={save} />}
    </div>
  );
}
