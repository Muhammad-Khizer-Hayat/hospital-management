const API = '';  // empty = same origin

let token = localStorage.getItem('token');
let currentUser = JSON.parse(localStorage.getItem('user') || 'null');

function switchTab(tab) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  const activeTab = document.querySelector(`.tab[onclick*="'${tab}'"]`);
  if (activeTab) activeTab.classList.add('active');
  document.getElementById('login-form').style.display = tab === 'login' ? 'block' : 'none';
  document.getElementById('register-form').style.display = tab === 'register' ? 'block' : 'none';
}

async function login(e) {
  e.preventDefault();
  const email = document.getElementById('login-email').value;
  const password = document.getElementById('login-password').value;
  try {
    const res = await fetch(`${API}/api/auth/login`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Login failed');
    localStorage.setItem('token', data.access_token);
    localStorage.setItem('user', JSON.stringify(data.user));
    token = data.access_token;
    currentUser = data.user;
    showDashboard();
  } catch (err) {
    showAuthError(err.message);
  }
}

async function register(e) {
  e.preventDefault();
  const body = {
    full_name: document.getElementById('reg-name').value,
    email: document.getElementById('reg-email').value,
    phone: document.getElementById('reg-phone').value,
    password: document.getElementById('reg-password').value,
    role: 'patient'
  };
  try {
    const res = await fetch(`${API}/api/auth/register`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Registration failed');
    showAuthError('Account created! Please login.', true);
    switchTab('login');
  } catch (err) {
    showAuthError(err.message);
  }
}

function showAuthError(msg, success = false) {
  const el = document.getElementById('auth-error');
  el.textContent = msg;
  el.className = success ? 'success-msg' : 'error-msg';
  el.style.display = 'block';
}

function showDashboard() {
  document.getElementById('auth-screen').style.display = 'none';
  document.getElementById('dashboard').style.display = 'block';
  document.getElementById('user-name').textContent = currentUser.full_name;
  document.getElementById('welcome-name').textContent = currentUser.full_name.split(' ')[0];
  loadHomeStats();
  loadDoctors();
}

function logout() {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  location.reload();
}

function showSection(name) {
  document.querySelectorAll('main section').forEach(s => s.style.display = 'none');
  document.getElementById(`section-${name}`).style.display = 'block';
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  const activeBtn = document.querySelector(`.nav-btn[onclick*="'${name}'"]`);
  if (activeBtn) activeBtn.classList.add('active');
  if (name === 'appointments') loadAppointments();
  if (name === 'records') loadPrescriptions();
  if (name === 'billing') loadBills();
}

async function apiCall(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json', ...(options.headers || {}) }
  });
  if (res.status === 401) { logout(); return null; }
  return res.json();
}

async function loadHomeStats() {
  const appts = await apiCall('/api/appointments/');
  const rxs = await apiCall('/api/prescriptions/');
  const bills = await apiCall('/api/billing/');
  if (appts) document.getElementById('stat-upcoming').textContent =
    appts.filter(a => a.status === 'pending' || a.status === 'confirmed').length;
  if (rxs) document.getElementById('stat-rx').textContent = rxs.length;
  if (bills) document.getElementById('stat-bills').textContent =
    bills.filter(b => b.payment_status === 'pending').length;
}

// Init
if (token && currentUser) showDashboard(); 