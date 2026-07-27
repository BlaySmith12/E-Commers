
const CD = {
    token: localStorage.getItem('token'),
    user: null,
    orders: [],
    wishlist: [],
    reviews: [],
    addresses: [],
    notifications: [],
    products: [],
    cartId: localStorage.getItem('cart_id') || (localStorage.setItem('cart_id','cart_'+Date.now()), localStorage.getItem('cart_id')),
    async api(url, opts = {}) {
        const headers = {'Content-Type':'application/json', ...(opts.headers||{})};
        if (this.token) headers['Authorization'] = 'Bearer ' + this.token;
        try {
            const r = await fetch(url, {...opts, headers});
            if (r.status === 401) { localStorage.removeItem('token'); localStorage.removeItem('user'); window.location.href='/login'; return null; }
            if (!r.ok) { const e = await r.json().catch(()=>({detail:'Error'})); throw new Error(e.detail || 'Request failed'); }
            return await r.json();
        } catch(e) { if(e.message!=='Failed to fetch') CD.toast(e.message, 'error'); throw e; }
    },
    toast(msg, type='info') {
        const c = document.getElementById('toastContainer');
        const t = document.createElement('div');
        t.className = 'cd-toast cd-toast-' + type;
        t.innerHTML = '<i class="bi bi-' + (type==='success'?'check-circle-fill':type==='error'?'exclamation-circle-fill':'info-circle-fill') + '"></i><span>' + msg + '</span>';
        c.appendChild(t);
        setTimeout(()=>t.classList.add('show'),10);
        setTimeout(()=>{t.classList.remove('show');setTimeout(()=>t.remove(),300);},3000);
    },
    logout() {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        window.location.href = '/login';
    }
};

function getCartId() { return CD.cartId; }

function toggleMobileSidebar() {
    document.getElementById('cdSidebar').classList.toggle('open');
    document.getElementById('mobileOverlay').classList.toggle('show');
}

function showSection(name, el) {
    document.querySelectorAll('.cd-section').forEach(s=>s.classList.remove('active'));
    document.getElementById('sec-'+name).classList.add('active');
    document.querySelectorAll('.cd-nav-link').forEach(n=>n.classList.remove('active'));
    if (el) el.classList.add('active');
    const titles = {overview:'Dashboard',orders:'My Orders',track:'Track Orders',wishlist:'Wishlist',reviews:'My Reviews',addresses:'Addresses',payment:'Payment Methods',coupons:'Coupons & Rewards',notifications:'Notifications',recent:'Recently Viewed',account:'Account Details',security:'Security',support:'Support'};
    document.getElementById('sectionTitle').textContent = titles[name]||'Dashboard';
    document.getElementById('cdSidebar').classList.remove('open');
    document.getElementById('mobileOverlay').classList.remove('show');
    if (name==='overview') loadOverview();
    if (name==='orders') loadOrders();
    if (name==='wishlist') loadWishlist();
    if (name==='reviews') loadReviews();
    if (name==='addresses') loadAddresses();
    if (name==='notifications') loadNotifications();
    if (name==='coupons') loadCoupons();
    if (name==='account') loadProfile();
    if (name==='recent') loadRecentViewed();
}

function doLogout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = '/';
}

function fmt(n) { return 'GHS ' + Number(n||0).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g,','); }
function timeAgo(d) { if(!d) return ''; const s=Math.floor((Date.now()-new Date(d))/1000); if(s<60)return 'Just now';if(s<3600)return Math.floor(s/60)+'m ago';if(s<86400)return Math.floor(s/3600)+'h ago';return Math.floor(s/86400)+'d ago'; }
function stars(n) { let s=''; for(let i=1;i<=5;i++) s+='<i class="bi bi-star'+(i<=n?'-fill':'')+'"></i>'; return s; }
function statusBadge(s) { const m={Pending:'pending',Processing:'processing',Shipped:'shipped',Delivered:'delivered',Cancelled:'cancelled',Refunded:'refunded'}; return '<span class="cd-badge cd-badge-'+(m[s]||'pending')+'">'+s+'</span>'; }

function trackStep(status) {
    const steps = ['Order Placed','Payment Confirmed','Processing','Packed','Shipped','Out for Delivery','Delivered'];
    const map = {'Pending':1,'Processing':3,'Shipped':5,'Delivered':7,'Cancelled':0};
    const current = map[status]||0;
    let h='<div class="cd-timeline">';
    steps.forEach((s,i)=>{
        const cls = i<current?'completed':i===current-1?'active':'pending';
        h+='<div class="cd-timeline-step '+cls+'"><div class="cd-timeline-dot"></div><div class="cd-timeline-label">'+s+'</div></div>';
    });
    return h+'</div>';
}

function addRecentViewed(product) {
    let rv = JSON.parse(localStorage.getItem('recentlyViewed')||'[]');
    rv = rv.filter(p=>p.id!==product.id);
    rv.unshift({id:product.id,name:product.name,slug:product.slug,price:product.price,discount_price:product.discount_price,image:product.image||''});
    if(rv.length>20) rv=rv.slice(0,20);
    localStorage.setItem('recentlyViewed',JSON.stringify(rv));
}

function productCard(p, actions) {
    const img = p.image || p.image_url || '/static/images/hero_bg.png';
    const price = p.discount_price ? '<span class="cd-price-old">'+fmt(p.price)+'</span> '+fmt(p.discount_price) : fmt(p.price);
    let acts = '';
    if (actions) acts = '<div class="cd-product-actions">'+actions+'</div>';
    return '<div class="cd-product-card"><a href="/product/'+p.slug+'" class="cd-product-img"><img src="'+img+'" alt="'+(p.name||'')+'" onerror="this.src=\'/static/images/hero_bg.png\'"></a><div class="cd-product-info"><a href="/product/'+p.slug+'" class="cd-product-name">'+(p.name||'Product')+'</a><div class="cd-product-price">'+price+'</div>'+acts+'</div></div>';
}

// ===== OVERVIEW =====
async function loadOverview() {
    try {
        const [orders, wishlist, reviews] = await Promise.all([
            CD.api('/api/orders?limit=100'),
            CD.api('/api/wishlists'),
            CD.api('/api/reviews/me')
        ]);
        CD.orders = orders || [];
        CD.wishlist = wishlist || [];
        CD.reviews = reviews || [];
        const total = CD.orders.length;
        const pending = CD.orders.filter(o=>o.status==='Pending'||o.status==='Processing').length;
        const completed = CD.orders.filter(o=>o.status==='Delivered').length;
        const spent = CD.orders.reduce((s,o)=>s+(o.total_amount||0),0);
        const points = Math.floor(spent*10);
        document.getElementById('statTotal').textContent = total;
        document.getElementById('statPending').textContent = pending;
        document.getElementById('statCompleted').textContent = completed;
        document.getElementById('statWishlist').textContent = CD.wishlist.length;
        document.getElementById('statSpent').textContent = fmt(spent);
        document.getElementById('statPoints').textContent = points.toLocaleString();
        // Recent orders
        const rl = document.getElementById('recentOrdersList');
        if (CD.orders.length===0) { rl.innerHTML='<div class="cd-empty-state"><i class="bi bi-bag"></i><p>No orders yet. <a href="/shop">Start shopping!</a></p></div>'; }
        else {
            let h='<div class="cd-table-wrap"><table class="cd-table"><thead><tr><th>Order</th><th>Date</th><th>Status</th><th>Total</th><th></th></tr></thead><tbody>';
            CD.orders.slice(0,5).forEach(o=>{
                h+='<tr><td>'+o.order_number+'</td><td>'+timeAgo(o.created_at)+'</td><td>'+statusBadge(o.status)+'</td><td>'+fmt(o.total_amount)+'</td><td><a class="cd-btn cd-btn-outline cd-btn-xs" onclick="viewOrder('+o.id+')">View</a></td></tr>';
            });
            h+='</tbody></table></div>';
            rl.innerHTML=h;
        }
        // Recommended products
        try {
            const prods = await CD.api('/api/products?limit=8');
            CD.products = prods || [];
            const rg = document.getElementById('recommendedGrid');
            if (CD.products.length===0) { rg.innerHTML='<div class="cd-empty-state"><p>No products available</p></div>'; }
            else { rg.innerHTML = CD.products.slice(0,4).map(p=>{
                const img = (p.images&&p.images.length>0) ? p.images.find(i=>i.is_primary)?.image_url||p.images[0].image_url : '';
                return productCard({...p,image:img}, '<button class="cd-btn cd-btn-primary cd-btn-xs" onclick="addToCart('+p.id+')">Add to Cart</button>');
            }).join(''); }
        } catch(e) { document.getElementById('recommendedGrid').innerHTML=''; }
        loadRecentViewed('recentViewedGrid');
    } catch(e) { console.error(e); }
}

function loadRecentViewed(containerId) {
    const rv = JSON.parse(localStorage.getItem('recentlyViewed')||'[]');
    const grid = document.getElementById(containerId||'recentFullGrid');
    if (!grid) return;
    if (rv.length===0) { grid.innerHTML='<div class="cd-empty-state"><i class="bi bi-clock-history"></i><p>No recently viewed products</p></div>'; return; }
    grid.innerHTML = rv.slice(0,4).map(p=>productCard(p,'<a href="/product/'+p.slug+'" class="cd-btn cd-btn-outline cd-btn-xs">View</a>')).join('');
}

// ===== ORDERS =====
let currentOrderFilter = '';
async function loadOrders(status) {
    if (status!==undefined) currentOrderFilter = status;
    const url = '/api/orders?limit=100' + (currentOrderFilter ? '&status='+currentOrderFilter : '');
    try {
        CD.orders = await CD.api(url) || [];
        renderOrders();
    } catch(e) { console.error(e); }
}
function filterOrders(status) {
    document.querySelectorAll('#orderTabs .cd-tab').forEach(t=>t.classList.remove('active'));
    event.target.classList.add('active');
    loadOrders(status);
}
function renderOrders() {
    const el = document.getElementById('ordersList');
    if (CD.orders.length===0) { el.innerHTML='<div class="cd-empty-state"><i class="bi bi-bag"></i><p>No orders found. <a href="/shop">Start shopping!</a></p></div>'; return; }
    el.innerHTML = CD.orders.map(o=>{
        const items = o.items||[];
        const canCancel = o.status==='Pending'||o.status==='Processing';
        return '<div class="cd-card cd-order-card"><div class="cd-order-header"><div><h6 class="mb-0">'+o.order_number+'</h6><small class="cd-text-muted">'+timeAgo(o.created_at)+'</small></div><div class="cd-order-header-right">'+statusBadge(o.status)+'<span class="cd-order-total">'+fmt(o.total_amount)+'</span></div></div><div class="cd-order-items">'+items.length+' item(s)</div><div class="cd-order-actions">'+(canCancel?'<button class="cd-btn cd-btn-danger cd-btn-xs" onclick="cancelOrder('+o.id+')">Cancel</button>':'')+'<button class="cd-btn cd-btn-outline cd-btn-xs" onclick="printInvoice('+o.id+')"><i class="bi bi-printer"></i> Invoice</button></div><div class="cd-order-timeline-toggle" onclick="toggleTimeline(this)"><i class="bi bi-chevron-down"></i> Order Timeline</div><div class="cd-order-timeline" style="display:none">'+trackStep(o.status)+'</div></div>';
    }).join('');
}
function toggleTimeline(el) {
    const tl = el.nextElementSibling;
    tl.style.display = tl.style.display==='none'?'block':'none';
    el.querySelector('i').className = tl.style.display==='none'?'bi bi-chevron-down':'bi bi-chevron-up';
}
async function viewOrder(id) {
    showSection('orders',document.querySelector('[data-section=orders]'));
    try {
        const o = await CD.api('/api/orders/'+id);
        if (!o) return;
        const items = o.items||[];
        let html = '<div class="cd-card"><div class="cd-section-header"><h5>'+o.order_number+'</h5>'+statusBadge(o.status)+'</div>';
        html += trackStep(o.status);
        html += '<div class="cd-order-detail-items mt-3"><h6>Items</h6>';
        items.forEach(i=>{ html+='<div class="cd-order-detail-item"><span>Product #'+i.product_id+' x '+i.quantity+'</span><span>'+fmt(i.price*i.quantity)+'</span></div>'; });
        html += '<div class="cd-order-detail-total"><span>Total</span><span>'+fmt(o.total_amount)+'</span></div></div>';
        if (o.status==='Pending'||o.status==='Processing') html+='<button class="cd-btn cd-btn-danger mt-3" onclick="cancelOrder('+o.id+')">Cancel Order</button>';
        html += '</div>';
        document.getElementById('ordersList').innerHTML = html;
    } catch(e) {}
}
async function cancelOrder(id) {
    if (!confirm('Are you sure you want to cancel this order?')) return;
    try {
        await CD.api('/api/orders/'+id+'/cancel',{method:'POST'});
        CD.toast('Order cancelled successfully','success');
        loadOrders();
    } catch(e) {}
}
function printInvoice(id) { window.print(); }

// ===== TRACK =====
async function trackOrder() {
    const num = document.getElementById('trackInput').value.trim();
    if (!num) { CD.toast('Please enter an order number','error'); return; }
    const el = document.getElementById('trackResult');
    el.innerHTML = '<div class="cd-skeleton cd-skeleton-card"></div>';
    try {
        const orders = await CD.api('/api/orders?limit=100');
        const o = orders.find(ord=>ord.order_number===num);
        if (!o) { el.innerHTML='<div class="cd-empty-state"><i class="bi bi-search"></i><p>Order not found</p></div>'; return; }
        el.innerHTML = '<div class="cd-card"><h5>'+o.order_number+'</h5>'+statusBadge(o.status)+'<div class="cd-order-total mt-2">'+fmt(o.total_amount)+'</div>'+trackStep(o.status)+'</div>';
    } catch(e) { el.innerHTML='<div class="cd-empty-state"><p>Error tracking order</p></div>'; }
}

// ===== WISHLIST =====
async function loadWishlist() {
    try {
        CD.wishlist = await CD.api('/api/wishlists') || [];
        document.getElementById('wishlistCount').textContent = CD.wishlist.length + ' items';
        const grid = document.getElementById('wishlistGrid');
        if (CD.wishlist.length===0) { grid.innerHTML='<div class="cd-empty-state"><i class="bi bi-heart"></i><p>Your wishlist is empty. <a href="/shop">Browse products!</a></p></div>'; return; }
        grid.innerHTML = CD.wishlist.map(w=>{
            const p = w.product;
            return productCard({...p,image:p.image_url}, '<button class="cd-btn cd-btn-primary cd-btn-xs" onclick="addToCart('+p.id+')">Add to Cart</button><button class="cd-btn cd-btn-outline cd-btn-xs" onclick="removeWishlist('+p.id+')"><i class="bi bi-heart-fill"></i></button>');
        }).join('');
    } catch(e) { console.error(e); }
}
async function addToCart(productId) {
    try {
        await CD.api('/api/cart/items?cart_id='+getCartId(),{method:'POST',body:JSON.stringify({product_id:productId,quantity:1})});
        CD.toast('Added to cart!','success');
        if (typeof updateCartCount==='function') updateCartCount();
    } catch(e) {}
}
async function removeWishlist(productId) {
    try {
        await CD.api('/api/wishlists/'+productId,{method:'DELETE'});
        CD.toast('Removed from wishlist','success');
        loadWishlist();
    } catch(e) {}
}

// ===== REVIEWS =====
async function loadReviews() {
    try {
        CD.reviews = await CD.api('/api/reviews/me') || [];
        const el = document.getElementById('reviewsList');
        if (CD.reviews.length===0) { el.innerHTML='<div class="cd-empty-state"><i class="bi bi-star"></i><p>No reviews yet. Share your experience!</p></div>'; return; }
        el.innerHTML = CD.reviews.map(r=>'<div class="cd-card cd-review-card"><div class="cd-review-header"><h6>'+(r.product_name||'Product')+'</h6><div class="cd-review-stars">'+stars(r.rating)+'</div></div><p class="cd-text-muted">'+(r.comment||'')+'</p><small class="cd-text-muted">'+timeAgo(r.created_at)+'</small><div class="cd-review-actions"><button class="cd-btn cd-btn-outline cd-btn-xs" onclick="editReview('+r.id+','+r.rating+',\''+(r.comment||'').replace(/'/g,"\\'")+'\','+r.product_id+')">Edit</button><button class="cd-btn cd-btn-danger cd-btn-xs" onclick="deleteReview('+r.id+')">Delete</button></div></div>').join('');
    } catch(e) { console.error(e); }
}
function showReviewModal(editId, rating, comment, productId) {
    document.getElementById('reviewModal').classList.remove('d-none');
    document.getElementById('revEditId').value = editId||'';
    document.getElementById('revProductId').value = productId||'';
    document.getElementById('revRating').value = rating||5;
    document.getElementById('revComment').value = comment||'';
    setRating(rating||5);
    document.getElementById('reviewModalTitle').textContent = editId?'Edit Review':'Write a Review';
}
function closeReviewModal() { document.getElementById('reviewModal').classList.add('d-none'); }
function setRating(n) {
    document.getElementById('revRating').value = n;
    document.querySelectorAll('#starRating i').forEach((s,i)=>{
        s.className = i<n ? 'bi bi-star-fill' : 'bi bi-star';
    });
}
function editReview(id,rating,comment,productId) { showReviewModal(id,rating,comment,productId); }
async function submitReview(e) {
    e.preventDefault();
    const editId = document.getElementById('revEditId').value;
    const data = { product_id: parseInt(document.getElementById('revProductId').value), rating: parseInt(document.getElementById('revRating').value), comment: document.getElementById('revComment').value };
    try {
        if (editId) { await CD.api('/api/reviews/'+editId,{method:'PUT',body:JSON.stringify({rating:data.rating,comment:data.comment})}); }
        else { await CD.api('/api/reviews',{method:'POST',body:JSON.stringify(data)}); }
        CD.toast('Review saved!','success');
        closeReviewModal();
        loadReviews();
    } catch(e) {}
}
async function deleteReview(id) {
    if (!confirm('Delete this review?')) return;
    try { await CD.api('/api/reviews/'+id,{method:'DELETE'}); CD.toast('Review deleted','success'); loadReviews(); } catch(e) {}
}

// ===== ADDRESSES =====
async function loadAddresses() {
    try {
        CD.addresses = await CD.api('/api/customers/me/addresses') || [];
        const grid = document.getElementById('addressGrid');
        if (CD.addresses.length===0) { grid.innerHTML='<div class="cd-empty-state"><i class="bi bi-house-door"></i><p>No addresses saved yet</p></div>'; return; }
        grid.innerHTML = CD.addresses.map(a=>'<div class="cd-card cd-address-card">'+(a.is_default?'<span class="cd-badge cd-badge-success">Default</span>':'')+'<p class="cd-address-text">'+a.street+', '+a.city+(a.state?', '+a.state:'')+', '+a.country+(a.zip_code?' '+a.zip_code:'')+'</p><div class="cd-address-actions"><button class="cd-btn cd-btn-outline cd-btn-xs" onclick="editAddress('+a.id+')">Edit</button>'+(a.is_default?'':'<button class="cd-btn cd-btn-outline cd-btn-xs" onclick="setDefault('+a.id+')">Set Default</button>')+'<button class="cd-btn cd-btn-danger cd-btn-xs" onclick="deleteAddress('+a.id+')">Delete</button></div></div>').join('');
    } catch(e) { console.error(e); }
}
function showAddressForm(addr) {
    document.getElementById('addressFormArea').classList.remove('d-none');
    document.getElementById('addressFormTitle').textContent = addr?'Edit Address':'Add Address';
    document.getElementById('addrId').value = addr?addr.id:'';
    document.getElementById('addrStreet').value = addr?addr.street:'';
    document.getElementById('addrCity').value = addr?addr.city:'';
    document.getElementById('addrState').value = addr?(addr.state||''):'';
    document.getElementById('addrCountry').value = addr?(addr.country||'Ghana'):'Ghana';
    document.getElementById('addrZip').value = addr?(addr.zip_code||''):'';
    document.getElementById('addrDefault').checked = addr?addr.is_default:false;
}
function hideAddressForm() { document.getElementById('addressFormArea').classList.add('d-none'); }
function editAddress(id) {
    const a = CD.addresses.find(x=>x.id===id);
    if (a) showAddressForm(a);
}
async function saveAddress(e) {
    e.preventDefault();
    const id = document.getElementById('addrId').value;
    const data = { street: document.getElementById('addrStreet').value, city: document.getElementById('addrCity').value, state: document.getElementById('addrState').value, country: document.getElementById('addrCountry').value, zip_code: document.getElementById('addrZip').value, is_default: document.getElementById('addrDefault').checked };
    try {
        if (id) { await CD.api('/api/customers/me/addresses/'+id,{method:'PUT',body:JSON.stringify(data)}); }
        else { await CD.api('/api/customers/me/addresses',{method:'POST',body:JSON.stringify(data)}); }
        CD.toast('Address saved!','success');
        hideAddressForm();
        loadAddresses();
    } catch(e) {}
}
async function setDefault(id) {
    const a = CD.addresses.find(x=>x.id===id);
    if (!a) return;
    try {
        await CD.api('/api/customers/me/addresses/'+id,{method:'PUT',body:JSON.stringify({...a,is_default:true})});
        CD.toast('Default address updated','success');
        loadAddresses();
    } catch(e) {}
}
async function deleteAddress(id) {
    if (!confirm('Delete this address?')) return;
    try { await CD.api('/api/customers/me/addresses/'+id,{method:'DELETE'}); CD.toast('Address deleted','success'); loadAddresses(); } catch(e) {}
}

// ===== COUPONS & REWARDS =====
function showCouponTab(tab, el) {
    document.querySelectorAll('#sec-coupons .cd-tab').forEach(t=>t.classList.remove('active'));
    el.classList.add('active');
    document.getElementById('couponsAvailable').classList.toggle('d-none',tab!=='available');
    document.getElementById('couponsRewards').classList.toggle('d-none',tab!=='rewards');
    if (tab==='rewards') loadRewards();
}
async function loadCoupons() {
    try {
        const coupons = await CD.api('/api/coupons/available') || [];
        const el = document.getElementById('couponsList');
        if (!coupons.length) { el.innerHTML='<div class="cd-empty-state"><i class="bi bi-ticket"></i><p>No coupons available at the moment</p></div>'; return; }
        el.innerHTML = coupons.filter(c=>c.is_active).map(c=>'<div class="cd-card cd-coupon-card"><div class="cd-coupon-discount">'+(c.discount_type==='percentage'?c.discount_value+'%':'GHS '+c.discount_value)+' OFF</div><div class="cd-coupon-code">'+c.code+'</div><p class="cd-text-muted small">'+(c.description||'Use this coupon on your next order')+'</p><div class="cd-coupon-meta"><span>Min. order: '+fmt(c.min_order_amount)+'</span>'+(c.end_date?'<span>Expires: '+new Date(c.end_date).toLocaleDateString()+'</span>':'')+'</div><button class="cd-btn cd-btn-outline cd-btn-xs" onclick="copyCoupon(\''+c.code+'\')"><i class="bi bi-clipboard"></i> Copy Code</button></div>').join('');
    } catch(e) {}
}
function copyCoupon(code) { navigator.clipboard.writeText(code).then(()=>CD.toast('Coupon code copied!','success')).catch(()=>CD.toast('Copy failed','error')); }
function loadRewards() {
    const spent = CD.orders.reduce((s,o)=>s+(o.total_amount||0),0);
    const points = Math.floor(spent*10);
    let tier='Bronze',next='Silver at 1,000 pts',pct=points/10;
    if (points>=10000) { tier='Platinum';next='Max tier reached';pct=100; }
    else if (points>=5000) { tier='Gold';next='Platinum at 10,000 pts';pct=((points-5000)/5000)*100; }
    else if (points>=1000) { tier='Silver';next='Gold at 5,000 pts';pct=((points-1000)/4000)*100; }
    document.getElementById('rewardPointsDisplay').textContent = points.toLocaleString();
    document.getElementById('tierName').textContent = tier;
    document.getElementById('tierNext').textContent = next;
    document.getElementById('tierProgress').style.width = Math.min(pct,100)+'%';
}

// ===== NOTIFICATIONS =====
async function loadNotifications() {
    try {
        CD.notifications = await CD.api('/api/notifications?limit=50') || [];
        const unread = CD.notifications.filter(n=>!n.is_read).length;
        const badge = document.getElementById('notifBadge');
        if (unread>0) { badge.textContent=unread; badge.classList.remove('d-none'); } else { badge.classList.add('d-none'); }
        const el = document.getElementById('notifList');
        if (CD.notifications.length===0) { el.innerHTML='<div class="cd-empty-state"><i class="bi bi-bell"></i><p>No notifications</p></div>'; return; }
        el.innerHTML = CD.notifications.map(n=>{
            const icons = {info:'info-circle',success:'check-circle',warning:'exclamation-triangle',error:'exclamation-circle'};
            return '<div class="cd-notif-item'+(n.is_read?'':' cd-unread')+'"><div class="cd-notif-icon"><i class="bi bi-'+(icons[n.type]||'bell')+'"></i></div><div class="cd-notif-body"><h6>'+n.title+'</h6><p class="cd-text-muted small">'+(n.message||'')+'</p><small class="cd-text-muted">'+timeAgo(n.created_at)+'</small></div><div class="cd-notif-actions">'+(n.is_read?'':'<button class="cd-btn cd-btn-outline cd-btn-xs" onclick="markRead('+n.id+')"><i class="bi bi-check"></i></button>')+'<button class="cd-btn cd-btn-outline cd-btn-xs" onclick="deleteNotif('+n.id+')"><i class="bi bi-trash"></i></button></div></div>';
        }).join('');
    } catch(e) { console.error(e); }
}
async function markRead(id) {
    try { await CD.api('/api/notifications/'+id+'/read',{method:'PATCH'}); loadNotifications(); } catch(e) {}
}
async function markAllRead() {
    try { await CD.api('/api/notifications/read-all',{method:'PATCH'}); CD.toast('All notifications marked as read','success'); loadNotifications(); } catch(e) {}
}
async function deleteNotif(id) {
    try { await CD.api('/api/notifications/'+id,{method:'DELETE'}); loadNotifications(); } catch(e) {}
}

// ===== PROFILE =====
async function loadProfile() {
    if (!CD.user) return;
    document.getElementById('profFirstName').value = CD.user.first_name||'';
    document.getElementById('profLastName').value = CD.user.last_name||'';
    document.getElementById('profEmail').value = CD.user.email||'';
    document.getElementById('profPhone').value = CD.user.phone||'';
    document.getElementById('profUsername').value = CD.user.username||'';
}
async function saveProfile(e) {
    e.preventDefault();
    try {
        CD.user = await CD.api('/api/customers/me',{method:'PATCH',body:JSON.stringify({
            first_name: document.getElementById('profFirstName').value,
            last_name: document.getElementById('profLastName').value,
            email: document.getElementById('profEmail').value,
            phone: document.getElementById('profPhone').value
        })});
        CD.toast('Profile updated!','success');
        updateTopbar();
    } catch(e) {}
}

// ===== SECURITY =====
async function changePassword(e) {
    e.preventDefault();
    const token = localStorage.getItem('token');
    if (!token) { window.location.href = '/login'; return; }
    const cp = document.getElementById('secCurrentPw').value;
    const np = document.getElementById('secNewPw').value;
    const cf = document.getElementById('secConfirmPw').value;
    if (!cp) { CD.toast('Please enter your current password','error'); return; }
    if (np !== cf) { CD.toast('Passwords do not match','error'); return; }
    if (np.length < 6) { CD.toast('Password must be at least 6 characters','error'); return; }
    if (cp === np) { CD.toast('New password must be different from current password','error'); return; }
    try {
        const resp = await fetch('/api/customers/me/change-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
            body: JSON.stringify({ current_password: cp, new_password: np })
        });
        const data = await resp.json();
        if (resp.ok) {
            CD.toast('Password changed successfully!','success');
            document.getElementById('secCurrentPw').value = '';
            document.getElementById('secNewPw').value = '';
            document.getElementById('secConfirmPw').value = '';
        } else {
            CD.toast(data.detail || 'Failed to change password','error');
        }
    } catch(ex) {
        CD.toast('Network error. Please try again.','error');
    }
}

// ===== SUPPORT (localStorage based) =====
function getTickets() { return JSON.parse(localStorage.getItem('supportTickets')||'[]'); }
function saveTickets(t) { localStorage.setItem('supportTickets',JSON.stringify(t)); }
function createTicket(e) {
    e.preventDefault();
    const tickets = getTickets();
    tickets.push({ id: Date.now(), subject: document.getElementById('ticketSubject').value, category: document.getElementById('ticketCategory').value, message: document.getElementById('ticketMessage').value, status: 'Open', created_at: new Date().toISOString(), replies: [] });
    saveTickets(tickets);
    document.getElementById('ticketSubject').value='';
    document.getElementById('ticketMessage').value='';
    CD.toast('Support ticket created!','success');
    renderTickets();
}
function renderTickets() {
    const tickets = getTickets();
    const el = document.getElementById('ticketsList');
    if (!tickets.length) { el.innerHTML='<div class="cd-empty-state"><i class="bi bi-headset"></i><p>No support tickets yet</p></div>'; return; }
    el.innerHTML = tickets.map(t=>'<div class="cd-card cd-ticket"><div class="cd-ticket-header"><h6>'+t.subject+'</h6>'+statusBadge(t.status)+'</div><p class="cd-text-muted small">'+t.category+' - '+timeAgo(t.created_at)+'</p><p>'+t.message+'</p>'+(t.status!=='Closed'?'<button class="cd-btn cd-btn-outline cd-btn-xs" onclick="closeTicket('+t.id+')">Close Ticket</button>':'<button class="cd-btn cd-btn-outline cd-btn-xs" onclick="reopenTicket('+t.id+')">Reopen</button>')+'</div>').join('');
}
function closeTicket(id) { const t=getTickets().find(x=>x.id===id); if(t){t.status='Closed';saveTickets(getTickets());CD.toast('Ticket closed','success');renderTickets();} }
function reopenTicket(id) { const t=getTickets().find(x=>x.id===id); if(t){t.status='Open';saveTickets(getTickets());CD.toast('Ticket reopened','success');renderTickets();} }

// ===== UPDATE TOPBAR =====
function updateTopbar() {
    if (!CD.user) return;
    document.getElementById('topbarUser').textContent = CD.user.username;
    document.getElementById('topbarAvatar').textContent = (CD.user.username||'U')[0].toUpperCase();
    document.getElementById('welcomeName').textContent = CD.user.first_name || CD.user.username;
    document.getElementById('userName').textContent = CD.user.username;
}

// ===== INIT =====
(function() {
    var loadEl = document.getElementById('cdLoading');
    function hideLoading() { if(loadEl) loadEl.classList.add('d-none'); }
    function showError(msg) { hideLoading(); CD.toast(msg,'error'); }

    if (!CD.token) { window.location.href='/login'; return; }

    fetch('/api/auth/me', {
        headers: {'Authorization':'Bearer ' + CD.token, 'Content-Type':'application/json'}
    }).then(function(r) {
        if (r.status === 401) {
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            window.location.href = '/login';
            return null;
        }
        if (!r.ok) throw new Error('Failed to load account');
        return r.json();
    }).then(function(user) {
        if (!user) return;
        CD.user = user;
        updateTopbar();
        hideLoading();
        try { var pp = localStorage.getItem('preferredPayment'); if(pp) document.getElementById('preferredPayment').value = pp; } catch(e) {}
        loadOverview();
        loadNotifications();
        renderTickets();
    }).catch(function(e) {
        showError('Failed to load. Please refresh the page.');
    });
})();
