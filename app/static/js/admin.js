/* ===================================================================
   ASAH'S PRIMENEST — Admin Header JavaScript
   Full functionality: Auth, Search, Notifications, Messages, Profile,
   Theme Toggle, Quick Add, Sidebar, Responsive
   =================================================================== */

/* ─── Global Fetch Interceptor: auto-inject Authorization header ─── */
(function () {
    const _origFetch = window.fetch;
    window.fetch = function (input, init) {
        if (!init) init = {};
        if (!init.headers) init.headers = {};
        const token = localStorage.getItem('admin_token');
        if (token) {
            if (init.headers instanceof Headers) {
                if (!init.headers.has('Authorization')) init.headers.set('Authorization', 'Bearer ' + token);
            } else if (Array.isArray(init.headers)) {
                const has = init.headers.some(h => h[0] === 'Authorization');
                if (!has) init.headers.push(['Authorization', 'Bearer ' + token]);
            } else if (typeof init.headers === 'object') {
                if (!('Authorization' in init.headers)) init.headers['Authorization'] = 'Bearer ' + token;
            }
        }
        return _origFetch.call(window, input, init);
    };
})();

const ADMIN = {
    token: localStorage.getItem('admin_token'),
    user: null,
    searchTimeout: null,
    pollInterval: null,

    API: '/api',

    // ─── Helpers ──────────────────────────────────────────────────────
    headers() {
        const h = { 'Content-Type': 'application/json' };
        if (this.token) h['Authorization'] = `Bearer ${this.token}`;
        return h;
    },

    async api(path, opts = {}) {
        try {
            const res = await fetch(`${this.API}${path}`, {
                headers: this.headers(),
                ...opts,
            });
            if (res.status === 401) { this.handleAuthError(); return null; }
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || `HTTP ${res.status}`);
            }
            return await res.json();
        } catch (e) {
            console.error(`API Error [${path}]:`, e);
            return null;
        }
    },

    toast(message, type = 'info') {
        const container = document.getElementById('admin-toast-container') || (() => {
            const c = document.createElement('div');
            c.id = 'admin-toast-container';
            c.style.cssText = 'position:fixed;top:80px;right:20px;z-index:10000;display:flex;flex-direction:column;gap:8px;';
            document.body.appendChild(c);
            return c;
        })();
        const colors = { success: '#198754', error: '#dc3545', warning: '#ffc107', info: '#0d6efd' };
        const icons = { success: 'bi-check-circle-fill', error: 'bi-x-circle-fill', warning: 'bi-exclamation-triangle-fill', info: 'bi-info-circle-fill' };
        const toast = document.createElement('div');
        toast.style.cssText = `background:#1a1717;border:1px solid ${colors[type]};color:#F6F9F9;padding:12px 16px;border-radius:8px;font-size:.85rem;display:flex;align-items:center;gap:8px;min-width:280px;box-shadow:0 4px 12px rgba(0,0,0,.4);animation:slideIn .3s ease;`;
        toast.innerHTML = `<i class="bi ${icons[type]}" style="color:${colors[type]}"></i><span>${message}</span>`;
        container.appendChild(toast);
        setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity .3s'; setTimeout(() => toast.remove(), 300); }, 4000);
    },

    timeAgo(dateStr) {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        const s = Math.floor((Date.now() - d.getTime()) / 1000);
        if (s < 60) return 'Just now';
        if (s < 3600) return `${Math.floor(s / 60)}m ago`;
        if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
        if (s < 604800) return `${Math.floor(s / 86400)}d ago`;
        return d.toLocaleDateString();
    },

    // ─── Authentication ───────────────────────────────────────────────
    handleAuthError() {
        this.token = null;
        localStorage.removeItem('admin_token');
        window.location.href = '/admin/login';
    },

    checkAuth() {
        if (!this.token) {
            window.location.href = '/admin/login';
            return false;
        }
        return true;
    },

    async loadUser() {
        const data = await this.api('/auth/me');
        if (data) {
            this.user = data;
            this.populateProfileUI();
            return true;
        }
        return false;
    },

    populateProfileUI() {
        if (!this.user) return;
        const u = this.user;
        const name = [u.first_name, u.last_name].filter(Boolean).join(' ') || u.username || 'Admin';
        const avatar = u.avatar_url || `https://ui-avatars.com/api/?name=${encodeURIComponent(name)}&background=F2660F&color=fff&size=80`;
        const roleName = u.role_name || (u.role && u.role.name) || 'Administrator';

        document.querySelectorAll('.admin-avatar').forEach(el => {
            if (el.tagName === 'IMG') el.src = avatar;
        });
        document.querySelectorAll('.admin-user-name').forEach(el => el.textContent = name);
        document.querySelectorAll('.admin-user-role').forEach(el => el.textContent = roleName);
    },

    // ─── Sidebar Toggle ──────────────────────────────────────────────
    initSidebar() {
        const sidebar = document.getElementById('admin-sidebar') || document.getElementById('sidebar');
        const desktopToggle = document.getElementById('desktopMenuToggle');
        const mobileToggle = document.getElementById('mobileMenuToggle');
        const overlay = document.getElementById('sidebar-overlay');

        if (desktopToggle && sidebar) {
            desktopToggle.addEventListener('click', () => {
                sidebar.classList.toggle('collapsed');
                localStorage.setItem('sidebar_collapsed', sidebar.classList.contains('collapsed'));
            });
            if (localStorage.getItem('sidebar_collapsed') === 'true') {
                sidebar.classList.add('collapsed');
            }
        }

        if (mobileToggle && sidebar) {
            mobileToggle.addEventListener('click', () => {
                const isOpen = sidebar.classList.toggle('mobile-open');
                if (overlay) {
                    overlay.style.display = isOpen ? 'block' : 'none';
                    overlay.classList.toggle('active', isOpen);
                }
                document.body.style.overflow = isOpen ? 'hidden' : '';
            });
        }

        if (overlay) {
            overlay.addEventListener('click', () => {
                sidebar?.classList.remove('mobile-open');
                overlay.classList.remove('active');
                overlay.style.display = 'none';
                document.body.style.overflow = '';
            });
        }

        document.querySelectorAll('.sidebar-link').forEach(link => {
            link.addEventListener('click', () => {
                if (window.innerWidth < 992) {
                    sidebar?.classList.remove('mobile-open');
                    overlay?.classList.remove('active');
                    document.body.style.overflow = '';
                }
            });
        });
    },

    // ─── Global Search ───────────────────────────────────────────────
    initSearch() {
        const input = document.getElementById('admin-search-input');
        const results = document.getElementById('search-results');
        const container = document.getElementById('search-container');
        if (!input || !results) return;

        input.addEventListener('input', () => {
            clearTimeout(this.searchTimeout);
            const q = input.value.trim();
            if (q.length < 2) { results.classList.add('d-none'); results.innerHTML = ''; return; }
            this.searchTimeout = setTimeout(() => this.doSearch(q), 300);
        });

        input.addEventListener('focus', () => {
            if (results.innerHTML.trim()) results.classList.remove('d-none');
        });

        document.addEventListener('click', (e) => {
            if (!container?.contains(e.target)) results.classList.add('d-none');
        });

        // Ctrl+K shortcut
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                input.focus();
                input.select();
            }
            if (e.key === 'Escape') {
                results.classList.add('d-none');
                input.blur();
            }
        });

        // Mobile search toggle
        const mobileBtn = document.getElementById('mobileSearchToggle');
        const searchForm = document.getElementById('search-form-wrapper');
        if (mobileBtn && searchForm) {
            mobileBtn.addEventListener('click', () => {
                searchForm.classList.toggle('mobile-search-open');
                if (searchForm.classList.contains('mobile-search-open')) input.focus();
            });
        }
    },

    async doSearch(q) {
        const results = document.getElementById('search-results');
        if (!results) return;
        results.innerHTML = '<div class="search-loading"><div class="spinner-border spinner-border-sm text-orange"></div> Searching...</div>';
        results.classList.remove('d-none');

        const data = await this.api(`/search?q=${encodeURIComponent(q)}`);
        if (!data || data.length === 0) {
            results.innerHTML = '<div class="search-empty"><i class="bi bi-search" style="opacity:.4;font-size:1.5rem"></i><p>No results found for "' + this.escHtml(q) + '"</p></div>';
            return;
        }

        const grouped = {};
        data.forEach(r => {
            if (!grouped[r.type]) grouped[r.type] = [];
            grouped[r.type].push(r);
        });

        const typeLabels = { product: 'Products', order: 'Orders', customer: 'Customers', category: 'Categories', brand: 'Brands', coupon: 'Coupons' };
        const typeIcons = { product: 'bi-box-seam', order: 'bi-receipt', customer: 'bi-person', category: 'bi-folder', brand: 'bi-tag', coupon: 'bi-ticket' };
        let html = '';
        for (const [type, items] of Object.entries(grouped)) {
            html += `<div class="search-group"><div class="search-group-title"><i class="bi ${typeIcons[type] || 'bi-search'}"></i> ${typeLabels[type] || type} <span class="search-count">${items.length}</span></div>`;
            items.forEach(r => {
                const thumb = r.image ? `<img src="${this.escHtml(r.image)}" class="search-thumb" alt="">` : `<div class="search-thumb-placeholder"><i class="bi ${typeIcons[type] || 'bi-search'}"></i></div>`;
                html += `<a href="${this.escHtml(r.url)}" class="search-result-item">${thumb}<div class="search-result-info"><div class="search-result-title">${this.escHtml(r.title)}</div>${r.subtitle ? `<div class="search-result-subtitle">${this.escHtml(r.subtitle)}</div>` : ''}</div></a>`;
            });
            html += '</div>';
        }
        results.innerHTML = html;
    },

    escHtml(s) {
        const d = document.createElement('div');
        d.textContent = s || '';
        return d.innerHTML;
    },

    // ─── Notifications ───────────────────────────────────────────────
    async loadNotificationCount() {
        const data = await this.api('/notifications/unread-count');
        const badge = document.getElementById('notif-badge');
        const count = data?.count || 0;
        if (badge) {
            badge.textContent = count > 99 ? '99+' : count;
            badge.style.display = count > 0 ? 'flex' : 'none';
        }
    },

    async loadNotifications() {
        const panel = document.getElementById('notif-panel-list');
        if (!panel) return;
        panel.innerHTML = '<div class="panel-loading"><div class="spinner-border spinner-border-sm text-orange"></div></div>';
        const data = await this.api('/notifications?limit=15');
        if (!data || data.length === 0) {
            panel.innerHTML = '<div class="panel-empty"><i class="bi bi-bell-slash"></i><p>No notifications yet</p></div>';
            return;
        }
        const iconMap = { info: 'bi-info-circle text-info', success: 'bi-check-circle text-success', warning: 'bi-exclamation-triangle text-warning', error: 'bi-x-circle text-danger' };
        panel.innerHTML = data.map(n => `
            <div class="panel-item ${n.is_read ? '' : 'unread'}" data-id="${n.id}" data-url="${this.getNotifUrl(n)}">
                <div class="panel-item-icon"><i class="bi ${iconMap[n.type] || iconMap.info}"></i></div>
                <div class="panel-item-content">
                    <div class="panel-item-title">${this.escHtml(n.title)}</div>
                    <div class="panel-item-text">${this.escHtml(n.message || '')}</div>
                    <div class="panel-item-time">${this.timeAgo(n.created_at)}</div>
                </div>
                <button class="panel-item-action" onclick="ADMIN.markNotifRead(${n.id})" title="Mark read"><i class="bi bi-check2"></i></button>
            </div>
        `).join('');
    },

    getNotifUrl(n) {
        const t = (n.title || '').toLowerCase();
        if (t.includes('order')) return '/admin/orders';
        if (t.includes('stock') || t.includes('inventory')) return '/admin/inventory';
        if (t.includes('review')) return '/admin/reviews';
        if (t.includes('customer') || t.includes('registration')) return '/admin/customers';
        if (t.includes('payment')) return '/admin/payments';
        return '/admin/notifications';
    },

    async markNotifRead(id) {
        await this.api(`/notifications/${id}/read`, { method: 'PATCH' });
        const el = document.querySelector(`.panel-item[data-id="${id}"]`);
        if (el) el.classList.remove('unread');
        this.loadNotificationCount();
    },

    async markAllNotifsRead() {
        await this.api('/notifications/read-all', { method: 'PATCH' });
        document.querySelectorAll('.panel-item.unread').forEach(el => el.classList.remove('unread'));
        this.loadNotificationCount();
        this.toast('All notifications marked as read', 'success');
    },

    // ─── Messages ────────────────────────────────────────────────────
    async loadMessageCount() {
        const data = await this.api('/messages/unread-count');
        const badge = document.getElementById('msg-badge');
        const count = data?.count || 0;
        if (badge) {
            badge.textContent = count > 99 ? '99+' : count;
            badge.style.display = count > 0 ? 'flex' : 'none';
        }
    },

    async loadMessages() {
        const panel = document.getElementById('msg-panel-list');
        if (!panel) return;
        panel.innerHTML = '<div class="panel-loading"><div class="spinner-border spinner-border-sm text-orange"></div></div>';
        const data = await this.api('/messages?limit=15');
        if (!data || data.length === 0) {
            panel.innerHTML = '<div class="panel-empty"><i class="bi bi-envelope-open"></i><p>No messages yet</p></div>';
            return;
        }
        const catIcons = { general: 'bi-chat-dots', support: 'bi-headset', order: 'bi-receipt', system: 'bi-gear' };
        panel.innerHTML = data.map(m => `
            <div class="panel-item ${m.is_read ? '' : 'unread'}" data-id="${m.id}">
                <div class="panel-item-icon"><i class="bi ${catIcons[m.category] || catIcons.general}"></i></div>
                <div class="panel-item-content">
                    <div class="panel-item-title">${this.escHtml(m.subject)}</div>
                    <div class="panel-item-text">${this.escHtml(m.sender_name)} — ${this.escHtml((m.body || '').substring(0, 60))}...</div>
                    <div class="panel-item-time">${this.timeAgo(m.created_at)}</div>
                </div>
                <button class="panel-item-action" onclick="ADMIN.markMsgRead(${m.id})" title="Mark read"><i class="bi bi-check2"></i></button>
            </div>
        `).join('');
    },

    async markMsgRead(id) {
        await this.api(`/messages/${id}/read`, { method: 'PATCH' });
        const el = document.querySelector(`.panel-item[data-id="${id}"]`);
        if (el) el.classList.remove('unread');
        this.loadMessageCount();
    },

    async markAllMsgsRead() {
        await this.api('/messages/read-all', { method: 'PATCH' });
        document.querySelectorAll('#msg-panel-list .panel-item.unread').forEach(el => el.classList.remove('unread'));
        this.loadMessageCount();
        this.toast('All messages marked as read', 'success');
    },

    // ─── Theme Toggle ────────────────────────────────────────────────
    initTheme() {
        const saved = localStorage.getItem('admin_theme') || 'dark';
        this.applyTheme(saved);
        const btn = document.getElementById('themeToggle');
        if (btn) {
            btn.addEventListener('click', () => {
                const current = document.documentElement.getAttribute('data-theme') || 'dark';
                const next = current === 'dark' ? 'light' : 'dark';
                this.applyTheme(next);
                localStorage.setItem('admin_theme', next);
            });
        }
    },

    applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        document.documentElement.setAttribute('data-bs-theme', theme);
        const icon = document.querySelector('#themeToggle i');
        if (icon) {
            icon.className = theme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-stars';
        }
        // Re-render charts if they exist (Chart.js needs color updates)
        if (typeof Chart !== 'undefined') {
            Chart.defaults.color = getComputedStyle(document.documentElement).getPropertyValue('--text-secondary').trim();
        }
    },

    // ─── Panel Toggle (Notifications / Messages) ─────────────────────
    initPanels() {
        document.querySelectorAll('[data-panel]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const panelId = btn.getAttribute('data-panel');
                const panel = document.getElementById(panelId);
                if (!panel) return;

                // Close other panels
                document.querySelectorAll('.header-panel.open').forEach(p => {
                    if (p.id !== panelId) p.classList.remove('open');
                });

                panel.classList.toggle('open');
                if (panel.classList.contains('open')) {
                    if (panelId === 'notif-panel') this.loadNotifications();
                    if (panelId === 'msg-panel') this.loadMessages();
                }
            });
        });

        document.addEventListener('click', (e) => {
            document.querySelectorAll('.header-panel.open').forEach(p => {
                if (!p.contains(e.target) && !e.target.closest('[data-panel]')) {
                    p.classList.remove('open');
                }
            });
        });
    },

    // ─── Sign Out ────────────────────────────────────────────────────
    signOut() {
        if (confirm('Are you sure you want to sign out?')) {
            this.token = null;
            localStorage.removeItem('admin_token');
            // Clear auth cookie
            document.cookie = 'admin_token=; path=/admin; max-age=0; SameSite=Lax';
            // Prevent back-button access
            history.pushState(null, '', '/admin/login');
            window.location.href = '/admin/login';
        }
    },

    // ─── Active Link ─────────────────────────────────────────────────
    highlightActiveLink() {
        const currentUrl = window.location.pathname;
        document.querySelectorAll('.sidebar-link').forEach(link => {
            link.classList.remove('active');
            const href = link.getAttribute('href');
            if (href === currentUrl || (href && currentUrl.startsWith(href) && href !== '/admin')) {
                link.classList.add('active');
            }
        });
        if (currentUrl === '/admin') {
            const dashLink = document.querySelector('.sidebar-link[href="/admin"]');
            if (dashLink) dashLink.classList.add('active');
        }
    },

    // ─── Initialize ──────────────────────────────────────────────────
    async init() {
        // Back-button prevention: if no token, redirect to login
        if (!this.token && !window.location.pathname.includes('/admin/login') &&
            !window.location.pathname.includes('/admin/forgot-password') &&
            !window.location.pathname.includes('/admin/reset-password')) {
            window.location.href = '/admin/login';
            return;
        }

        // Prevent back-button from returning to protected pages after logout
        if (window.location.pathname.includes('/admin/login')) {
            history.pushState(null, '', '/admin/login');
        }

        window.addEventListener('popstate', function(e) {
            if (!localStorage.getItem('admin_token') &&
                !window.location.pathname.includes('/admin/login') &&
                !window.location.pathname.includes('/admin/forgot-password') &&
                !window.location.pathname.includes('/admin/reset-password')) {
                window.location.href = '/admin/login';
            }
        });

        this.initSidebar();
        this.initSearch();
        this.initTheme();
        this.initPanels();
        this.highlightActiveLink();

        if (this.token) {
            const loaded = await this.loadUser();
            if (!loaded) {
                this.handleAuthError();
                return;
            }
            this.loadNotificationCount();
            this.loadMessageCount();

            // Poll for updates every 60 seconds
            this.pollInterval = setInterval(() => {
                this.loadNotificationCount();
                this.loadMessageCount();
            }, 60000);
        }
    }
};

document.addEventListener('DOMContentLoaded', () => ADMIN.init());
