// ── State ─────────────────────────────────────────────────────────────────
const state = {
  profile: null,
  tailored: null,
  tailoredDiff: [],
  activeTab: 'edit',
  activeSection: 'personal',
  selectedTemplate: 'ember',
  dirty: false,
  templates: [],
  settings: { anthropic_api_key_set: false, anthropic_api_key_preview: '', openai_api_key_set: false, openai_api_key_preview: '' },
};

// ── Boot ──────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  await Promise.all([loadProfile(), loadTemplates(), loadSettings()]);
  renderSidebar();
  renderContent();
});

// ── API helpers ───────────────────────────────────────────────────────────
async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

// ── Load / Save ───────────────────────────────────────────────────────────
async function loadProfile() {
  state.profile = await api('GET', '/api/profile');
  state.dirty = false;
}

async function saveProfile() {
  const btn = document.getElementById('save-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>';
  try {
    collectFormData();
    await api('PUT', '/api/profile', state.profile);
    state.dirty = false;
    updateDirtyIndicator();
    toast('Saved ✓', 'success');
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '💾 Save';
  }
}

async function loadTemplates() {
  state.templates = await api('GET', '/api/templates');
}

async function loadSettings() {
  state.settings = await api('GET', '/api/settings');
}

async function saveSettings() {
  const antKey = (document.getElementById('s-ant-key')?.value || '').trim();
  const oaiKey = (document.getElementById('s-oai-key')?.value || '').trim();
  const btn = document.getElementById('settings-save-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>';
  try {
    await api('PUT', '/api/settings', { anthropic_api_key: antKey, openai_api_key: oaiKey });
    await loadSettings();
    renderContent();
    toast('Settings saved ✓', 'success');
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = 'Save Keys';
  }
}

// ── Collect form data back into state.profile ─────────────────────────────
function collectFormData() {
  const p = state.profile;

  // Meta
  if (document.getElementById('f-name')) {
    p.meta = {
      name: v('f-name'), tagline: v('f-tagline'),
      email: v('f-email'), phone: v('f-phone'),
      web: v('f-web'), linkedin: v('f-linkedin'), location: v('f-location'),
    };
  }

  // Summary
  const sumEl = document.getElementById('f-summary');
  if (sumEl) {
    if (typeof p.summary === 'object' && p.summary !== null) {
      p.summary.default = sumEl.value;
    } else {
      p.summary = sumEl.value;
    }
  }

  // Experience — collected live via collectEntry calls
  // Skills — collected live
  // Education — collected live
}

function v(id) {
  const el = document.getElementById(id);
  return el ? el.value.trim() : '';
}

function markDirty() {
  if (!state.dirty) {
    state.dirty = true;
    updateDirtyIndicator();
  }
}

function updateDirtyIndicator() {
  const title = document.querySelector('.topbar-title');
  if (!title) return;
  const name = state.profile?.meta?.name || 'CV';
  title.innerHTML = `${name} ${state.dirty ? '<span style="color:var(--accent)">●</span>' : '<span>—</span>'} CV Tailor`;
}

// ── Navigation ────────────────────────────────────────────────────────────
function setTab(tab) {
  state.activeTab = tab;
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  renderContent();
}

function setSection(section) {
  if (state.activeTab !== 'edit') {
    state.activeTab = 'edit';
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === 'edit'));
  }
  state.activeSection = section;
  document.querySelectorAll('.sidebar-item[data-section]').forEach(el =>
    el.classList.toggle('active', el.dataset.section === section)
  );
  renderContent();
}

// ── Render ────────────────────────────────────────────────────────────────
function renderSidebar() {
  const sections = [
    { id: 'personal', icon: '👤', label: 'Personal Info' },
    { id: 'summary',  icon: '📝', label: 'Summary' },
    { id: 'experience', icon: '💼', label: 'Experience' },
    { id: 'education', icon: '🎓', label: 'Education' },
    { id: 'skills',   icon: '⚡', label: 'Skills' },
    { id: 'metrics',  icon: '📊', label: 'Metrics' },
    { id: 'speaking', icon: '🎤', label: 'Speaking' },
    { id: 'ventures', icon: '🚀', label: 'Ventures' },
    { id: 'projects', icon: '🔧', label: 'Projects' },
  ];

  const nav = document.getElementById('sidebar-nav');
  nav.innerHTML = sections.map(s => `
    <div class="sidebar-item ${state.activeSection === s.id && state.activeTab === 'edit' ? 'active' : ''}"
         data-section="${s.id}" onclick="setSection('${s.id}')">
      <span class="icon">${s.icon}</span>${s.label}
    </div>
  `).join('');
}

function renderContent() {
  const el = document.getElementById('content');
  renderSidebar();

  switch (state.activeTab) {
    case 'edit':     el.innerHTML = renderEditTab(); attachEditListeners(); break;
    case 'tailor':   el.innerHTML = renderTailorTab(); break;
    case 'export':   el.innerHTML = renderExportTab(); break;
    case 'settings': el.innerHTML = renderSettingsTab(); break;
  }
  updateDirtyIndicator();
}

// ── Edit tab ──────────────────────────────────────────────────────────────
function renderEditTab() {
  switch (state.activeSection) {
    case 'personal':   return renderPersonal();
    case 'summary':    return renderSummary();
    case 'experience': return renderExperience();
    case 'education':  return renderEducation();
    case 'skills':     return renderSkills();
    case 'metrics':    return renderMetrics();
    case 'speaking':   return renderSpeaking();
    case 'ventures':   return renderVentures();
    case 'projects':   return renderProjects();
    default:           return '<p>Select a section.</p>';
  }
}

function attachEditListeners() {
  document.querySelectorAll('input, textarea, select').forEach(el => {
    el.addEventListener('input', markDirty);
  });
}

// ── Personal Info ─────────────────────────────────────────────────────────
function setMeta(field, val) {
  state.profile.meta = state.profile.meta || {};
  state.profile.meta[field] = val;
  markDirty();
}

function setSummary(val) {
  if (typeof state.profile.summary === 'object' && state.profile.summary !== null) {
    state.profile.summary.default = val;
  } else {
    state.profile.summary = val;
  }
  markDirty();
}

function renderPersonal() {
  const m = state.profile?.meta || {};
  return `
    <div class="card">
      <div class="card-header"><h2>Personal Information</h2></div>
      <div class="card-body">
        <div class="form-grid">
          <div class="form-group span-2"><label>Full Name</label><input id="f-name" type="text" value="${esc(m.name)}" placeholder="Your name" oninput="setMeta('name',this.value)"></div>
          <div class="form-group span-2"><label>Current Role / Tagline</label><input id="f-tagline" type="text" value="${esc(m.tagline)}" placeholder="e.g. Chief Marketing Officer" oninput="setMeta('tagline',this.value)"></div>
          <div class="form-group"><label>Email</label><input id="f-email" type="email" value="${esc(m.email)}" placeholder="you@example.com" oninput="setMeta('email',this.value)"></div>
          <div class="form-group"><label>Phone</label><input id="f-phone" type="text" value="${esc(m.phone)}" placeholder="+1 555 000 0000" oninput="setMeta('phone',this.value)"></div>
          <div class="form-group"><label>Website</label><input id="f-web" type="text" value="${esc(m.web)}" placeholder="yoursite.com" oninput="setMeta('web',this.value)"></div>
          <div class="form-group"><label>LinkedIn</label><input id="f-linkedin" type="text" value="${esc(m.linkedin)}" placeholder="linkedin.com/in/you" oninput="setMeta('linkedin',this.value)"></div>
          <div class="form-group span-2"><label>Location</label><input id="f-location" type="text" value="${esc(m.location)}" placeholder="City, Country" oninput="setMeta('location',this.value)"></div>
        </div>
      </div>
    </div>`;
}

// ── Summary ───────────────────────────────────────────────────────────────
function renderSummary() {
  const s = state.profile?.summary || {};
  const text = typeof s === 'string' ? s : (s.default || '');
  return `
    <div class="card">
      <div class="card-header"><h2>Profile Summary</h2></div>
      <div class="card-body">
        <div class="form-group">
          <label>Summary Text</label>
          <textarea id="f-summary" rows="6" placeholder="A compelling overview of your background and value..." oninput="setSummary(this.value)">${esc(text)}</textarea>
        </div>
        <p class="text-sm text-muted mt-2">This is your default summary. AI tailoring may select or adjust it per role.</p>
      </div>
    </div>`;
}

// ── Experience ────────────────────────────────────────────────────────────
function renderExperience() {
  const exp = state.profile?.experience || [];
  return `
    <div class="flex-between mb-2">
      <h2 style="font-size:15px;font-weight:600;">Experience</h2>
      <button class="btn btn-primary btn-sm" onclick="addExperience()">+ Add Entry</button>
    </div>
    ${exp.length === 0 ? emptyState('💼', 'No experience yet', 'Click "Add Entry" to add your first role.') : ''}
    <div id="exp-list">
      ${exp.map((e, i) => renderExpEntry(e, i)).join('')}
    </div>`;
}

function renderExpEntry(e, i) {
  const roles = (e.roles || []).map((r, ri) => `
    <div class="role-item" id="role-${i}-${ri}">
      <input type="text" value="${esc(r.title)}" placeholder="Job Title" oninput="updateRole(${i},${ri},'title',this.value);markDirty()">
      <input type="text" value="${esc(r.period)}" placeholder="Period (e.g. Jan 2022 – Dec 2023)" style="max-width:220px" oninput="updateRole(${i},${ri},'period',this.value);markDirty()">
      <button class="btn btn-danger btn-sm" onclick="removeRole(${i},${ri})">✕</button>
    </div>`).join('');

  const bullets = (e.bullets || []).map((b, bi) => {
    const text = typeof b === 'string' ? b : (b.text || '');
    const tags = typeof b === 'object' ? (b.tags || []).join(', ') : '';
    const weight = typeof b === 'object' ? (b.weight ?? 5) : 5;
    return `
      <div class="bullet-item" id="bullet-${i}-${bi}">
        <div style="flex:1">
          <textarea oninput="updateBullet(${i},${bi},'text',this.value);markDirty()" placeholder="Describe your achievement...">${esc(text)}</textarea>
          <div class="bullet-meta">
            <span class="text-muted text-sm">Tags:</span>
            <input type="text" value="${esc(tags)}" placeholder="e.g. marketing, analytics" oninput="updateBullet(${i},${bi},'tags',this.value);markDirty()" style="flex:1;min-width:0">
            <span class="text-muted text-sm">Weight:</span>
            <input type="number" min="1" max="10" value="${weight}" class="weight-input" oninput="updateBullet(${i},${bi},'weight',+this.value);markDirty()">
          </div>
        </div>
        <button class="btn btn-danger" onclick="removeBullet(${i},${bi})">✕</button>
      </div>`;
  }).join('');

  return `
    <div class="entry-card" id="exp-entry-${i}">
      <div class="entry-header" onclick="toggleEntry('exp-body-${i}')">
        <div class="entry-header-left">
          <span class="entry-title">${esc(e.company || 'New Entry')}</span>
          <span class="entry-subtitle">${esc(e.location || '')}</span>
        </div>
        <span class="entry-toggle" id="toggle-exp-body-${i}">▼</span>
      </div>
      <div class="entry-body open" id="exp-body-${i}">
        <div class="form-grid mb-2">
          <div class="form-group">
            <label>Company</label>
            <input type="text" value="${esc(e.company)}" placeholder="Company Name"
              oninput="state.profile.experience[${i}].company=this.value;markDirty();document.querySelector('#exp-entry-${i} .entry-title').textContent=this.value||'New Entry'">
          </div>
          <div class="form-group">
            <label>Location</label>
            <input type="text" value="${esc(e.location)}" placeholder="City or Remote"
              oninput="state.profile.experience[${i}].location=this.value;markDirty()">
          </div>
          <div class="form-group span-2">
            <label>Company Note (optional)</label>
            <input type="text" value="${esc(e.subtitle)}" placeholder="Brief company description shown under role"
              oninput="state.profile.experience[${i}].subtitle=this.value;markDirty()">
          </div>
        </div>

        <div class="mb-2">
          <div class="flex-between mb-1">
            <label>Roles</label>
            <button class="btn btn-ghost btn-sm" onclick="addRole(${i})">+ Role</button>
          </div>
          <div id="roles-${i}">${roles}</div>
        </div>

        <div>
          <div class="flex-between mb-1">
            <label>Bullets <span class="text-muted text-sm">(weight 1–10 sets AI priority)</span></label>
            <button class="btn btn-ghost btn-sm" onclick="addBullet(${i})">+ Bullet</button>
          </div>
          <div id="bullets-${i}">${bullets}</div>
        </div>

        <div class="mt-3 flex gap-2" style="justify-content:flex-end">
          <button class="btn btn-danger" onclick="removeExperience(${i})">Remove Entry</button>
        </div>
      </div>
    </div>`;
}

function toggleEntry(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.toggle('open');
  const toggle = document.getElementById('toggle-' + id);
  if (toggle) toggle.textContent = el.classList.contains('open') ? '▼' : '▶';
}

function addExperience() {
  state.profile.experience = state.profile.experience || [];
  state.profile.experience.push({ company: '', subtitle: '', location: '', roles: [{ title: '', period: '' }], bullets: [] });
  markDirty();
  renderContent();
  setTimeout(() => window.scrollTo(0, document.body.scrollHeight), 50);
}

function removeExperience(i) {
  state.profile.experience.splice(i, 1);
  markDirty();
  renderContent();
}

function addRole(i) {
  state.profile.experience[i].roles = state.profile.experience[i].roles || [];
  state.profile.experience[i].roles.push({ title: '', period: '' });
  markDirty();
  renderContent();
}

function removeRole(i, ri) {
  state.profile.experience[i].roles.splice(ri, 1);
  markDirty();
  renderContent();
}

function updateRole(i, ri, field, val) {
  state.profile.experience[i].roles[ri][field] = val;
}

function addBullet(i) {
  state.profile.experience[i].bullets = state.profile.experience[i].bullets || [];
  state.profile.experience[i].bullets.push({ text: '', tags: [], weight: 5 });
  markDirty();
  renderContent();
}

function removeBullet(i, bi) {
  state.profile.experience[i].bullets.splice(bi, 1);
  markDirty();
  renderContent();
}

function updateBullet(i, bi, field, val) {
  const b = state.profile.experience[i].bullets[bi];
  if (typeof b === 'string') {
    state.profile.experience[i].bullets[bi] = { text: b, tags: [], weight: 5 };
  }
  if (field === 'tags') {
    state.profile.experience[i].bullets[bi].tags = val.split(',').map(t => t.trim()).filter(Boolean);
  } else {
    state.profile.experience[i].bullets[bi][field] = val;
  }
}

// ── Education ─────────────────────────────────────────────────────────────
function renderEducation() {
  const edu = state.profile?.education || [];
  return `
    <div class="flex-between mb-2">
      <h2 style="font-size:15px;font-weight:600;">Education</h2>
      <button class="btn btn-primary btn-sm" onclick="addEducation()">+ Add</button>
    </div>
    ${edu.length === 0 ? emptyState('🎓', 'No education entries', '') : ''}
    ${edu.map((e, i) => `
      <div class="entry-card">
        <div class="entry-header" onclick="toggleEntry('edu-body-${i}')">
          <div class="entry-header-left">
            <span class="entry-title">${esc(e.school || 'New Entry')}</span>
            <span class="entry-subtitle">${esc(e.degree || '')}</span>
          </div>
          <span class="entry-toggle" id="toggle-edu-body-${i}">▼</span>
        </div>
        <div class="entry-body open" id="edu-body-${i}">
          <div class="form-grid">
            <div class="form-group span-2">
              <label>School / Institution</label>
              <input type="text" value="${esc(e.school)}" oninput="state.profile.education[${i}].school=this.value;markDirty()">
            </div>
            <div class="form-group span-2">
              <label>Degree / Programme</label>
              <input type="text" value="${esc(e.degree)}" oninput="state.profile.education[${i}].degree=this.value;markDirty()">
            </div>
            <div class="form-group">
              <label>Period</label>
              <input type="text" value="${esc(e.period)}" placeholder="Sept 2018 – Jun 2022" oninput="state.profile.education[${i}].period=this.value;markDirty()">
            </div>
            <div class="form-group">
              <label>Location</label>
              <input type="text" value="${esc(e.location)}" placeholder="City or Remote" oninput="state.profile.education[${i}].location=this.value;markDirty()">
            </div>
            <div class="form-group span-2">
              <label>Details (grade, thesis, etc.)</label>
              <input type="text" value="${esc(Array.isArray(e.details) ? e.details.join('; ') : (e.details || ''))}"
                oninput="state.profile.education[${i}].details=this.value;markDirty()">
            </div>
          </div>
          <div class="mt-3 flex gap-2" style="justify-content:flex-end">
            <button class="btn btn-danger btn-sm" onclick="state.profile.education.splice(${i},1);markDirty();renderContent()">Remove</button>
          </div>
        </div>
      </div>`).join('')}`;
}

function addEducation() {
  state.profile.education = state.profile.education || [];
  state.profile.education.push({ school: '', degree: '', period: '', location: '', details: '' });
  markDirty();
  renderContent();
}

// ── Skills ────────────────────────────────────────────────────────────────
function renderSkills() {
  const skills = state.profile?.skills || {};
  const groups = (skills.groups || []);
  return `
    <div class="flex-between mb-2">
      <h2 style="font-size:15px;font-weight:600;">Skills</h2>
      <button class="btn btn-primary btn-sm" onclick="addSkillGroup()">+ Add Group</button>
    </div>
    ${groups.length === 0 ? emptyState('⚡', 'No skill groups', '') : ''}
    ${groups.map((g, gi) => `
      <div class="skill-group">
        <div class="skill-group-header">
          <input type="text" value="${esc(g.name)}" placeholder="Group name (e.g. Technical, Leadership)"
            oninput="state.profile.skills.groups[${gi}].name=this.value;markDirty()">
          <button class="btn btn-danger btn-sm" onclick="state.profile.skills.groups.splice(${gi},1);markDirty();renderContent()">Remove group</button>
        </div>
        <div class="skill-group-body">
          <div class="skills-tags" id="skill-tags-${gi}">
            ${(g.items || []).map((item, ii) => `
              <span class="skill-tag">${esc(item)}
                <button onclick="removeSkillItem(${gi},${ii})">×</button>
              </span>`).join('')}
          </div>
          <div class="flex gap-2 mt-2">
            <input type="text" id="new-skill-${gi}" placeholder="Type a skill and press Enter"
              onkeydown="if(event.key==='Enter'){addSkillItem(${gi});event.preventDefault()}">
            <button class="btn btn-ghost btn-sm" onclick="addSkillItem(${gi})">Add</button>
          </div>
        </div>
      </div>`).join('')}`;
}

function addSkillGroup() {
  state.profile.skills = state.profile.skills || { groups: [] };
  state.profile.skills.groups = state.profile.skills.groups || [];
  state.profile.skills.groups.push({ name: '', items: [], tags: [] });
  markDirty();
  renderContent();
}

function addSkillItem(gi) {
  const input = document.getElementById(`new-skill-${gi}`);
  const val = input.value.trim();
  if (!val) return;
  state.profile.skills.groups[gi].items = state.profile.skills.groups[gi].items || [];
  state.profile.skills.groups[gi].items.push(val);
  input.value = '';
  markDirty();
  renderContent();
}

function removeSkillItem(gi, ii) {
  state.profile.skills.groups[gi].items.splice(ii, 1);
  markDirty();
  renderContent();
}

// ── Metrics ───────────────────────────────────────────────────────────────
function renderMetrics() {
  const metrics = state.profile?.metrics || [];
  return `
    <div class="flex-between mb-2">
      <h2 style="font-size:15px;font-weight:600;">Key Metrics</h2>
      <button class="btn btn-primary btn-sm" onclick="addMetric()">+ Add Metric</button>
    </div>
    <p class="text-sm text-muted mb-2">Quantified achievements shown at the top of the CV. AI picks the 4 most relevant.</p>
    ${metrics.map((m, i) => `
      <div class="card mb-2">
        <div class="card-body">
          <div class="form-grid cols-3">
            <div class="form-group">
              <label>Value</label>
              <input type="text" value="${esc(m.value)}" placeholder="e.g. €1.5bn" oninput="state.profile.metrics[${i}].value=this.value;markDirty()">
            </div>
            <div class="form-group span-2">
              <label>Label</label>
              <input type="text" value="${esc(m.label)}" placeholder="Pipeline generated" oninput="state.profile.metrics[${i}].label=this.value;markDirty()">
            </div>
            <div class="form-group span-2">
              <label>Tags (comma-separated)</label>
              <input type="text" value="${esc((m.tags||[]).join(', '))}" oninput="state.profile.metrics[${i}].tags=this.value.split(',').map(t=>t.trim()).filter(Boolean);markDirty()">
            </div>
            <div class="form-group">
              <label>Weight (1–10)</label>
              <input type="number" min="1" max="10" value="${m.weight||5}" oninput="state.profile.metrics[${i}].weight=+this.value;markDirty()">
            </div>
          </div>
          <div class="mt-2 flex" style="justify-content:flex-end">
            <button class="btn btn-danger btn-sm" onclick="state.profile.metrics.splice(${i},1);markDirty();renderContent()">Remove</button>
          </div>
        </div>
      </div>`).join('')}
    ${metrics.length === 0 ? emptyState('📊', 'No metrics yet', 'Add quantified achievements like pipeline, revenue, or growth numbers.') : ''}`;
}

function addMetric() {
  state.profile.metrics = state.profile.metrics || [];
  state.profile.metrics.push({ value: '', label: '', tags: [], weight: 5 });
  markDirty();
  renderContent();
}

// ── Speaking ──────────────────────────────────────────────────────────────
function renderSpeaking() {
  const speaking = state.profile?.speaking || [];
  return `
    <div class="flex-between mb-2">
      <h2 style="font-size:15px;font-weight:600;">Speaking & Appearances</h2>
      <button class="btn btn-primary btn-sm" onclick="addSpeaking()">+ Add</button>
    </div>
    ${speaking.map((s, i) => {
      const title = typeof s === 'string' ? s : (s.title || s.name || '');
      const year = typeof s === 'object' ? (s.year || '') : '';
      const tags = typeof s === 'object' ? (s.tags || []).join(', ') : '';
      return `
        <div class="card mb-2">
          <div class="card-body">
            <div class="form-grid">
              <div class="form-group span-2">
                <label>Title / Event</label>
                <input type="text" value="${esc(title)}" oninput="updateSpeaking(${i},'title',this.value);markDirty()">
              </div>
              <div class="form-group">
                <label>Year</label>
                <input type="text" value="${esc(year)}" placeholder="2024" oninput="updateSpeaking(${i},'year',this.value);markDirty()">
              </div>
              <div class="form-group">
                <label>Tags</label>
                <input type="text" value="${esc(tags)}" oninput="updateSpeaking(${i},'tags',this.value);markDirty()">
              </div>
            </div>
            <div class="mt-2 flex" style="justify-content:flex-end">
              <button class="btn btn-danger btn-sm" onclick="state.profile.speaking.splice(${i},1);markDirty();renderContent()">Remove</button>
            </div>
          </div>
        </div>`;
    }).join('')}
    ${speaking.length === 0 ? emptyState('🎤', 'No speaking entries', '') : ''}`;
}

function addSpeaking() {
  state.profile.speaking = state.profile.speaking || [];
  state.profile.speaking.push({ title: '', year: '', tags: [] });
  markDirty();
  renderContent();
}

function updateSpeaking(i, field, val) {
  if (typeof state.profile.speaking[i] === 'string') {
    state.profile.speaking[i] = { title: state.profile.speaking[i], year: '', tags: [] };
  }
  if (field === 'tags') {
    state.profile.speaking[i].tags = val.split(',').map(t => t.trim()).filter(Boolean);
  } else {
    state.profile.speaking[i][field] = val;
  }
}

// ── Ventures ──────────────────────────────────────────────────────────────
function renderVentures() {
  const ventures = state.profile?.ventures || [];
  return `
    <div class="flex-between mb-2">
      <h2 style="font-size:15px;font-weight:600;">Ventures & Projects</h2>
      <button class="btn btn-primary btn-sm" onclick="addVenture()">+ Add</button>
    </div>
    ${ventures.map((v, i) => `
      <div class="card mb-2">
        <div class="card-body">
          <div class="form-grid">
            <div class="form-group"><label>Name</label><input type="text" value="${esc(v.name||v)}" oninput="updateVenture(${i},'name',this.value);markDirty()"></div>
            <div class="form-group"><label>Period</label><input type="text" value="${esc(v.period||'')}" placeholder="2022 – Present" oninput="updateVenture(${i},'period',this.value);markDirty()"></div>
            <div class="form-group"><label>URL</label><input type="text" value="${esc(v.url||'')}" oninput="updateVenture(${i},'url',this.value);markDirty()"></div>
            <div class="form-group span-2"><label>Description</label><input type="text" value="${esc(v.description||'')}" oninput="updateVenture(${i},'description',this.value);markDirty()"></div>
          </div>
          <div class="mt-2 flex" style="justify-content:flex-end">
            <button class="btn btn-danger btn-sm" onclick="state.profile.ventures.splice(${i},1);markDirty();renderContent()">Remove</button>
          </div>
        </div>
      </div>`).join('')}
    ${ventures.length === 0 ? emptyState('🚀', 'No ventures yet', '') : ''}`;
}

function addVenture() {
  state.profile.ventures = state.profile.ventures || [];
  state.profile.ventures.push({ name: '', url: '', description: '' });
  markDirty();
  renderContent();
}

function updateVenture(i, field, val) {
  if (typeof state.profile.ventures[i] === 'string') {
    state.profile.ventures[i] = { name: state.profile.ventures[i] };
  }
  state.profile.ventures[i][field] = val;
}

// ── Projects ──────────────────────────────────────────────────────────────
function renderProjects() {
  const projects = state.profile?.projects || [];
  return `
    <div class="flex-between mb-2">
      <h2 style="font-size:15px;font-weight:600;">Other Projects</h2>
      <button class="btn btn-primary btn-sm" onclick="addProject()">+ Add</button>
    </div>
    ${projects.map((p, i) => `
      <div class="card mb-2">
        <div class="card-body">
          <div class="form-grid">
            <div class="form-group span-2"><label>Project Name</label><input type="text" value="${esc(p.name||'')}" oninput="state.profile.projects[${i}].name=this.value;markDirty()"></div>
            <div class="form-group span-2"><label>URL (without https://)</label><input type="text" value="${esc(p.url||'')}" placeholder="github.com/user/repo" oninput="state.profile.projects[${i}].url=this.value;markDirty()"></div>
            <div class="form-group span-2"><label>Description</label><textarea rows="2" oninput="state.profile.projects[${i}].description=this.value;markDirty()">${esc(p.description||'')}</textarea></div>
          </div>
          <div class="mt-2 flex" style="justify-content:flex-end">
            <button class="btn btn-danger btn-sm" onclick="state.profile.projects.splice(${i},1);markDirty();renderContent()">Remove</button>
          </div>
        </div>
      </div>`).join('')}
    ${projects.length === 0 ? emptyState('🔧', 'No projects yet', '') : ''}`;
}

function addProject() {
  state.profile.projects = state.profile.projects || [];
  state.profile.projects.push({ name: '', url: '', description: '' });
  markDirty();
  renderContent();
}

// ── Tailor tab ────────────────────────────────────────────────────────────
function renderTailorTab() {
  const hasTailored = !!state.tailored;
  return `
    <div class="tailor-panel">
      <div class="card mb-4">
        <div class="card-header"><h2>Tailor to a Position</h2></div>
        <div class="card-body">
          <div class="form-grid cols-1 mb-2">
            <div class="form-group">
              <label>Job Posting URL <span class="text-muted">(optional — paste the URL to auto-fetch the JD)</span></label>
              <input type="url" id="t-url" value="${esc(state._lastUrl||'')}" placeholder="https://company.com/jobs/role">
            </div>
          </div>
          <div class="form-grid">
            <div class="form-group">
              <label>Role</label>
              <input type="text" id="t-role" value="${esc(state._lastRole||'')}" placeholder="VP of Marketing">
            </div>
            <div class="form-group">
              <label>Company</label>
              <input type="text" id="t-company" value="${esc(state._lastCompany||'')}" placeholder="Acme Corp">
            </div>
            <div class="form-group span-2">
              <label>Keywords / Emphasis <span class="text-muted">(comma-separated — optional)</span></label>
              <input type="text" id="t-keywords" value="${esc(state._lastKeywords||'')}" placeholder="e.g. demand generation, ABM, pipeline">
            </div>
            <div class="form-group span-2">
              <label>Job Description Text <span class="text-muted">(paste here if no URL, or leave blank)</span></label>
              <textarea id="t-jd" rows="4" placeholder="Paste the full job description...">${esc(state._lastJD||'')}</textarea>
            </div>
          </div>
          <div class="flex gap-3 mt-3" style="align-items:center;flex-wrap:wrap">
            <div class="toggle-wrap">
              <div class="toggle ${state._useAI !== false ? 'on' : ''}" id="ai-toggle" onclick="toggleAI()"></div>
              <span class="toggle-label">Use AI tailoring (Claude)</span>
            </div>
            <div class="toggle-wrap">
              <div class="toggle ${state._rewrite ? 'on' : ''}" id="rewrite-toggle" onclick="toggleRewrite()"></div>
              <span class="toggle-label">Allow bullet rewrites</span>
            </div>
            <button class="btn btn-primary" id="tailor-btn" onclick="runTailor()">✨ Tailor CV</button>
          </div>
        </div>
      </div>

      ${hasTailored ? renderDiff() : `
        <div class="empty-state">
          <div class="empty-icon">✨</div>
          <h3>Ready to tailor</h3>
          <p>Fill in the details above and click "Tailor CV" to see AI-suggested changes.</p>
        </div>`}
    </div>`;
}

function toggleAI() {
  state._useAI = state._useAI === false ? true : false;
  document.getElementById('ai-toggle').classList.toggle('on', state._useAI !== false);
}
function toggleRewrite() {
  state._rewrite = !state._rewrite;
  document.getElementById('rewrite-toggle').classList.toggle('on', !!state._rewrite);
}

async function runTailor() {
  const btn = document.getElementById('tailor-btn');
  const url = document.getElementById('t-url').value.trim();
  const role = document.getElementById('t-role').value.trim();
  const company = document.getElementById('t-company').value.trim();
  const keywords = document.getElementById('t-keywords').value.trim();
  const jd = document.getElementById('t-jd').value.trim();

  if (!role && !url && !jd) {
    toast('Please enter a role, URL, or job description.', 'error');
    return;
  }

  // Save last values
  state._lastUrl = url;
  state._lastRole = role;
  state._lastCompany = company;
  state._lastKeywords = keywords;
  state._lastJD = jd;

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Tailoring…';

  try {
    // Auto-save first
    collectFormData();
    await api('PUT', '/api/profile', state.profile);

    const res = await api('POST', '/api/tailor', {
      url, jd_text: jd, role, company,
      emphasis: keywords ? keywords.split(',').map(k => k.trim()).filter(Boolean) : [],
      use_ai: state._useAI !== false,
      rewrite: !!state._rewrite,
    });
    state.tailored = res.tailored;
    state.tailoredDiff = res.diff;
    state._fit = res.fit || null;
    state._jdPreview = res.jd_preview;
    state._urlWarning = res.url_warning || null;
    renderContent();
    if (res.url_warning) {
      toast(`⚠️ ${res.url_warning}`, '');
    } else {
      toast(`Tailored! ${res.diff.length} section(s) changed.`, 'success');
    }
  } catch (e) {
    toast(e.message, 'error');
    // Also show inline so it's impossible to miss
    const content = document.getElementById('content');
    const banner = document.createElement('div');
    banner.style.cssText = 'background:#fee2e2;border:1px solid #fca5a5;color:#7f1d1d;padding:12px 16px;border-radius:8px;margin-bottom:16px;font-size:13px;';
    banner.innerHTML = `<strong>Error:</strong> ${e.message}`;
    content.prepend(banner);
    setTimeout(() => banner.remove(), 8000);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '✨ Tailor CV';
  }
}

function renderDiff() {
  const diff = state.tailoredDiff;
  if (diff.length === 0) {
    return `<div class="card"><div class="card-body"><p class="text-muted">No changes detected — your CV already matches well!</p></div></div>`;
  }

  const blocks = diff.map(d => {
    let badge = `<span class="diff-badge ${d.type}">${d.type}</span>`;
    let body = '';

    if (d.section === 'summary') {
      body = `
        <div class="diff-rows">
          <div class="diff-row">
            <div class="diff-label">Original</div>
            <div class="diff-text-original">${esc(d.original)}</div>
          </div>
          <div class="diff-row">
            <div class="diff-label">Tailored</div>
            <div class="diff-text-tailored">${esc(d.tailored)}</div>
          </div>
        </div>`;
    } else if (d.section === 'metrics') {
      body = `
        <div class="diff-rows">
          <p class="text-sm text-muted">${d.removed_count} metric(s) removed — kept ${d.tailored_count} of ${d.original_count} most relevant.</p>
        </div>`;
    } else if (d.section === 'experience') {
      let orderHtml = '';
      if (d.order_changed) {
        orderHtml = `
          <div class="diff-row">
            <div class="diff-label">New order</div>
            <ul class="diff-list">${d.tailored_order.map(c => `<li>${esc(c)}</li>`).join('')}</ul>
          </div>`;
      }
      let bulletHtml = (d.bullet_changes || []).map(bc => `
        <div class="diff-row">
          <div class="diff-label">${esc(bc.company)} — removed bullets</div>
          ${bc.removed.map(b => `<div class="removed-item">${esc(b)}</div>`).join('')}
        </div>`).join('');
      body = `<div class="diff-rows">${orderHtml}${bulletHtml}</div>`;
    } else if (d.section === 'skills') {
      body = `
        <div class="diff-rows">
          <div class="diff-row">
            <div class="diff-label">Tailored order</div>
            <ul class="diff-list">${d.tailored_order.map(g => `<li>${esc(g)}</li>`).join('')}</ul>
          </div>
        </div>`;
    } else if (d.section === 'speaking') {
      body = `<div class="diff-rows"><p class="text-sm text-muted">${d.removed_count} entry/entries removed — kept ${d.tailored_count}.</p></div>`;
    }

    return `
      <div class="diff-block">
        <div class="diff-block-header">
          <h3>${esc(d.label)}</h3>${badge}
        </div>
        ${body}
      </div>`;
  }).join('');

  // Fit analysis panel
  let focusHtml = '';
  const fit = state._fit;
  if (fit) {
    const score = fit.fit_score ?? 0;
    const label = fit.fit_label || '';
    const scoreColor = score >= 75 ? 'var(--fit-high)' : score >= 50 ? 'var(--fit-mid)' : 'var(--fit-low)';

    const meterDots = Array.from({length: 10}, (_, i) =>
      `<span class="fit-dot ${i < Math.round(score / 10) ? 'on' : ''}" style="${i < Math.round(score / 10) ? `background:${scoreColor}` : ''}"></span>`
    ).join('');

    const section = (icon, title, items, cls) => items?.length ? `
      <div class="fit-section">
        <div class="fit-section-title">${icon} ${title}</div>
        <ul class="fit-list ${cls}">${items.map(s => `<li>${esc(s)}</li>`).join('')}</ul>
      </div>` : '';

    focusHtml = `
      <div class="fit-panel">
        <div class="fit-header">
          <div class="fit-score-block">
            <div class="fit-meter">${meterDots}</div>
            <span class="fit-score-num" style="color:${scoreColor}">${score}%</span>
            <span class="fit-label" style="color:${scoreColor}">${esc(label)}</span>
          </div>
          ${fit.fit_summary ? `<p class="fit-summary">${esc(fit.fit_summary)}</p>` : ''}
        </div>
        ${section('🎯', 'Key points to hit', fit.key_points, 'fit-list-key')}
        ${section('✅', 'Strengths for this role', fit.strengths, 'fit-list-strength')}
        ${section('⚠️', 'Gaps to address', fit.gaps, 'fit-list-gap')}
        ${section('📝', 'Suggested CV improvements', fit.suggestions, 'fit-list-suggest')}
      </div>`;
  }

  return `
    <div>
      <div class="flex-between mb-3">
        <h2 style="font-size:15px;font-weight:600;">${diff.length} change(s) to apply</h2>
        <div class="flex gap-2">
          <button class="btn btn-secondary btn-sm" onclick="discardTailored()">Discard</button>
          <button class="btn btn-primary" onclick="applyTailored()">Apply &amp; Save Tailored CV →</button>
        </div>
      </div>
      ${state._urlWarning ? `<div style="background:#fef3c7;border:1px solid #fcd34d;color:#92400e;padding:10px 14px;border-radius:6px;font-size:12px;margin-bottom:10px;">⚠️ ${esc(state._urlWarning)}</div>` : ''}
      ${focusHtml}
      ${state._jdPreview ? `<div class="jd-preview"><strong>JD preview:</strong> ${esc(state._jdPreview)}…</div>` : ''}
      <div class="mt-3">${blocks}</div>
    </div>`;
}

async function applyTailored() {
  if (!state.tailored) return;
  const role = state._lastRole || 'tailored';
  const company = state._lastCompany || '';
  const filename = [role, company].filter(Boolean).join('_').replace(/\s+/g, '_').toLowerCase();
  try {
    const res = await fetch('/api/export/pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: state.tailored, template: state.selectedTemplate, filename }),
    });
    if (!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${filename}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
    toast('Tailored PDF downloaded!', 'success');
  } catch (e) {
    toast(e.message, 'error');
  }
}

function discardTailored() {
  state.tailored = null;
  state.tailoredDiff = [];
  state._fit = null;
  renderContent();
}

// ── Settings tab ──────────────────────────────────────────────────────────
function renderSettingsTab() {
  const s = state.settings;

  const keyRow = (id, label, isSet, preview, placeholder) => `
    <div class="form-group mb-3">
      <label>${label} ${isSet ? `<code class="api-key-status set" style="font-size:11px;padding:2px 6px;">✓ ${esc(preview)}</code>` : '<span class="api-key-status unset" style="font-size:11px;">not set</span>'}</label>
      <div class="input-with-toggle">
        <input type="password" id="${id}" placeholder="${isSet ? 'Enter new key to replace…' : placeholder}"
          autocomplete="off" spellcheck="false">
        <button class="show-btn" onclick="toggleKeyVisibility('${id}')">Show</button>
      </div>
    </div>`;

  const hasAny = s.anthropic_api_key_set || s.openai_api_key_set;
  return `
    <div style="max-width:560px">
      <div class="card mb-4">
        <div class="card-header">
          <h2>AI Provider Keys</h2>
          <span class="api-key-status ${hasAny ? 'set' : 'unset'}">${hasAny ? '✓ AI enabled' : '✗ Not set'}</span>
        </div>
        <div class="card-body">
          ${keyRow('s-ant-key', 'Anthropic (Claude)', s.anthropic_api_key_set, s.anthropic_api_key_preview, 'sk-ant-api03-…')}
          ${keyRow('s-oai-key', 'OpenAI (gpt-4o-mini)', s.openai_api_key_set, s.openai_api_key_preview, 'sk-…')}
          <button class="btn btn-primary" id="settings-save-btn" onclick="saveSettings()">Save Keys</button>
          <div class="info-box mt-3">
            <strong>Priority:</strong> Anthropic is used when set; OpenAI is the fallback. Both can coexist.<br>
            Keys are stored locally in <code>data/settings.yaml</code> and never leave your machine.<br>
            Without any key, tailoring uses tag-based (deterministic) mode.
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header"><h2>About</h2></div>
        <div class="card-body">
          <p class="text-sm text-muted" style="line-height:1.7">
            CV Tailor runs entirely on your machine.<br>
            Your CV data is stored in <code>data/master_profile.yaml</code>.<br>
            Generated PDFs go to <code>data/output/</code>.<br>
            <strong>⌘S / Ctrl+S</strong> saves the current section.
          </p>
        </div>
      </div>
    </div>`;
}

function toggleKeyVisibility(id) {
  const input = document.getElementById(id);
  if (!input) return;
  const isPassword = input.type === 'password';
  input.type = isPassword ? 'text' : 'password';
  // Find the sibling show-btn
  const btn = input.parentElement.querySelector('.show-btn');
  if (btn) btn.textContent = isPassword ? 'Hide' : 'Show';
}

// ── Export tab ────────────────────────────────────────────────────────────
function renderExportTab() {
  const templates = state.templates;
  const templateColors = {
    ember: 'Warm cream & rust — editorial feel',
    meridian: 'Clean white & black — modern minimal',
    slate: 'Cool gray tones — professional',
    verdant: 'Natural greens — fresh & approachable',
    folio: 'Artistic purple tones — creative',
  };
  return `
    <div style="max-width:700px">
      <div class="card mb-4">
        <div class="card-header"><h2>Choose Template</h2></div>
        <div class="card-body">
          <div class="export-grid">
            ${templates.map(t => `
              <div class="template-card template-${t.name} ${state.selectedTemplate === t.name ? 'selected' : ''}"
                   onclick="selectTemplate('${t.name}')">
                <div class="template-preview"></div>
                <div class="template-name">${t.name.charAt(0).toUpperCase() + t.name.slice(1)}</div>
                <div class="template-desc">${templateColors[t.name] || t.description || ''}</div>
              </div>`).join('')}
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header"><h2>Export</h2></div>
        <div class="card-body">
          <div class="flex gap-3" style="flex-wrap:wrap;align-items:center">
            <button class="btn btn-primary" onclick="exportMasterPDF()">
              ⬇ Download Base CV (${state.selectedTemplate})
            </button>
            ${state.tailored ? `
              <button class="btn btn-secondary" onclick="applyTailored()">
                ⬇ Download Tailored CV
              </button>` : ''}
          </div>
          ${state.tailored ? '' : `<p class="text-sm text-muted mt-2">Go to the Tailor tab to generate a tailored version for a specific role.</p>`}
        </div>
      </div>
    </div>`;
}

function selectTemplate(name) {
  state.selectedTemplate = name;
  renderContent();
}

async function exportMasterPDF() {
  const btn = event.target;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Generating…';
  try {
    collectFormData();
    const name = (state.profile?.meta?.name || 'cv').replace(/\s+/g, '_').toLowerCase();
    const res = await fetch('/api/export/pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: state.profile, template: state.selectedTemplate, filename: name }),
    });
    if (!res.ok) throw new Error('Export failed');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${name}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
    toast('PDF downloaded!', 'success');
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `⬇ Download Base CV (${state.selectedTemplate})`;
  }
}

// ── Utilities ─────────────────────────────────────────────────────────────
function esc(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function emptyState(icon, title, body) {
  return `<div class="empty-state"><div class="empty-icon">${icon}</div><h3>${title}</h3><p>${body}</p></div>`;
}

function toast(msg, type = '') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `show ${type}`;
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove('show'), 3500);
}

// Keyboard shortcut: Cmd/Ctrl+S to save
document.addEventListener('keydown', e => {
  if ((e.metaKey || e.ctrlKey) && e.key === 's') {
    e.preventDefault();
    saveProfile();
  }
});
