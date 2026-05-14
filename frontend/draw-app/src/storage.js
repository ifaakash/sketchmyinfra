const STORAGE_KEY = "smi_drawings";

function getAll() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveAll(drawings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(drawings));
}

export const localDrawings = {
  list() {
    return getAll();
  },

  get(id) {
    return getAll().find((d) => d.id === id) || null;
  },

  create(drawing) {
    const all = getAll();
    const item = {
      id: crypto.randomUUID(),
      title: drawing.title || "Untitled",
      data: drawing.data,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    all.unshift(item);
    saveAll(all);
    return item;
  },

  update(id, updates) {
    const all = getAll();
    const idx = all.findIndex((d) => d.id === id);
    if (idx === -1) return null;
    if (updates.title !== undefined) all[idx].title = updates.title;
    if (updates.data !== undefined) all[idx].data = updates.data;
    all[idx].updated_at = new Date().toISOString();
    saveAll(all);
    return all[idx];
  },

  delete(id) {
    saveAll(getAll().filter((d) => d.id !== id));
  },

  clear() {
    localStorage.removeItem(STORAGE_KEY);
  },
};
