'use strict';
var P = (function() {
    var S = {sid:0, prods:[], cats:[], cart:[], selIdx:-1, mode:'qty', payMeth:'cash', payInp:'', sq:'', cashBal:0};

    function vnd(n) {
        return new Intl.NumberFormat('vi-VN', {style:'currency', currency:'VND'}).format(n || 0);
    }
    function $(id) { return document.getElementById(id); }

    function show(id) {
        var screens = document.querySelectorAll('.scr');
        for (var i = 0; i < screens.length; i++) screens[i].classList.remove('on');
        $(id).classList.add('on');
    }

    function init() {
        var initEl = $('bhx-init');
        if (initEl) {
            try { var d = JSON.parse(initEl.textContent); S.sid = d.shift_id; } catch(e) {}
        }
        var searchEl = $('search');
        if (searchEl) {
            searchEl.addEventListener('input', function(e) { S.sq = e.target.value.toLowerCase(); rProds(); });
        }
        var phoneEl = $('c-phone');
        if (phoneEl) {
            phoneEl.addEventListener('input', function(e) {
                var p = e.target.value.trim();
                if (p.length >= 10) {
                    rpc('/bhx/pos/search_customer', {phone: p}).then(function(r) {
                        if (r && r.customer) { $('c-name').value = r.customer.name; }
                    });
                }
            });
        }
        fetchData();
    }

    function fetchData() {
        rpc('/bhx/pos/get_data', {shift_id: S.sid}).then(function(r) {
            if (r) {
                S.prods = r.products || [];
                S.cats = r.categories || [];
                S.cashBal = parseFloat(r.current_cash_total) || 0;
                rCats();
                rProds();
            }
        }).catch(function() {
            $('pgrid').innerHTML = '<div class="ploading">Loi tai san pham.</div>';
        });
    }

    function rCats() {
        var c = $('cat-tabs');
        c.innerHTML = '<button class="cb on" onclick="P.cat(\'all\',this)">Tat ca</button>';
        for (var i = 0; i < S.cats.length; i++) {
            var x = S.cats[i];
            var b = document.createElement('button');
            b.className = 'cb';
            b.textContent = x.name;
            (function(catId, btn) {
                btn.onclick = function() { cat(catId, btn); };
            })(x.id, b);
            c.appendChild(b);
        }
    }

    function rProds() {
        var g = $('pgrid');
        var l = S.prods;
        if (S.ac && S.ac !== 'all') {
            l = l.filter(function(p) { return p.categ_id && p.categ_id[0] == S.ac; });
        }
        if (S.sq) {
            l = l.filter(function(p) {
                var name = (p.display_name || p.name || '').toLowerCase();
                return name.indexOf(S.sq) !== -1 || (p.barcode && p.barcode.toLowerCase().indexOf(S.sq) !== -1);
            });
        }
        if (!l.length) { g.innerHTML = '<div class="ploading">Khong tim thay san pham.</div>'; return; }

        var html = '';
        for (var i = 0; i < l.length; i++) {
            var p = l[i];
            var imgHtml = p.image_128 ? '<img src="data:image/png;base64,' + p.image_128 + '"/>' : '\uD83D\uDECD\uFE0F';
            var uom = p.uom_id ? p.uom_id[1] : '';
            var pName = (p.display_name || p.name || '').trim();
            if (!pName) {
                console.warn('Product missing name:', p.id);
                pName = 'ID: ' + p.id;
            }
            html += '<div class="pcard" onclick="P.add(' + p.id + ')">'
                + '<div class="pimg">' + imgHtml + '</div>'
                + '<div class="pbody">'
                + '<div class="pname">' + pName + '</div>'
                + '<div style="display:flex;align-items:baseline"><span class="pprice">' + vnd(p.list_price) + '</span><span class="puom">/ ' + uom + '</span></div>'
                + '</div></div>';
        }
        g.innerHTML = html;
    }

    function rCart() {
        var a = $('cart-list');
        if (!S.cart.length) {
            a.innerHTML = '<div class="cart-empty"><b>\uD83D\uDED2</b><p>Chua co san pham</p></div>';
            $('btn-pay').disabled = true;
            $('ft-sub').textContent = '0 \u20AB';
            $('ft-disc').textContent = '-0 \u20AB';
            $('ft-total').textContent = '0 \u20AB';
            return;
        }
        var sub = 0, disc = 0, html = '';
        for (var i = 0; i < S.cart.length; i++) {
            var it = S.cart[i];
            var st = it.price * it.qty * (1 - it.disc / 100);
            var d = it.price * it.qty * it.disc / 100;
            sub += it.price * it.qty;
            disc += d;
            var activeClass = (i === S.selIdx) ? ' active' : '';
            var discTxt = it.disc ? ' (-' + it.disc + '%)' : '';
            var itName = (it.display_name || it.name || '').trim() || ('ID: ' + it.product_id);
            html += '<div class="ci' + activeClass + '" onclick="P.sel(' + i + ')">'
                + '<div class="ci-info"><div class="ci-name">' + itName + '</div>'
                + '<div class="ci-meta">' + vnd(it.price) + ' \u00D7 ' + it.qty + discTxt + '</div></div>'
                + '<div class="ci-qty"><button class="qb" onclick="event.stopPropagation();P.chg(' + i + ',-1)">\u2212</button>'
                + '<span class="qv">' + it.qty + '</span>'
                + '<button class="qb" onclick="event.stopPropagation();P.chg(' + i + ',1)">+</button></div>'
                + '<div class="ci-sub">' + vnd(st) + '</div>'
                + '<button class="ci-del" onclick="event.stopPropagation();P.rm(' + i + ')">\u2715</button></div>';
        }
        a.innerHTML = html;
        var hdr = document.querySelector('.cart-hdr');
        if (hdr) hdr.textContent = '\uD83D\uDED2 Gio hang ( ' + S.cart.length + ' )';
        
        $('ft-sub').textContent = vnd(sub);
        $('ft-disc').textContent = '-' + vnd(disc);
        $('ft-total').textContent = vnd(sub - disc);
        $('btn-pay').disabled = false;
        
        // Auto-scroll to bottom if new item added
        a.scrollTop = a.scrollHeight;
    }

    function add(id) {
        var p = null;
        for (var i = 0; i < S.prods.length; i++) { if (S.prods[i].id === id) { p = S.prods[i]; break; } }
        if (!p) return;
        var e = null;
        for (var j = 0; j < S.cart.length; j++) { if (S.cart[j].product_id === id) { e = S.cart[j]; break; } }
        if (e) { e.qty += 1; }
        else {
            S.cart.push({
                product_id: p.id, 
                name: p.name, 
                display_name: p.display_name,
                price: p.list_price, 
                qty: 1, 
                disc: 0, 
                uom: p.uom_id ? p.uom_id[1] : ''
            });
            S.selIdx = S.cart.length - 1;
        }
        rCart();
    }

    function chg(i, d) {
        S.cart[i].qty += d;
        if (S.cart[i].qty <= 0) { S.cart.splice(i, 1); if (S.selIdx >= S.cart.length) S.selIdx = S.cart.length - 1; }
        rCart();
    }
    function rm(i) { S.cart.splice(i, 1); if (S.selIdx >= S.cart.length) S.selIdx = S.cart.length - 1; rCart(); }
    function sel(i) { S.selIdx = i; rCart(); }

    function cat(id, btn) {
        S.ac = id;
        var btns = document.querySelectorAll('.cb');
        for (var i = 0; i < btns.length; i++) btns[i].classList.remove('on');
        if (btn) btn.classList.add('on');
        rProds();
    }

    function setMode(m) {
        S.mode = m;
        var modes = document.querySelectorAll('.npad-mode');
        for (var i = 0; i < modes.length; i++) modes[i].classList.remove('on');
        var sel = document.querySelector('.npad-mode[data-mode="' + m + '"]');
        if (sel) sel.classList.add('on');
    }

    function np(k) {
        if (S.selIdx < 0 || S.selIdx >= S.cart.length) return;
        var it = S.cart[S.selIdx];
        if (k === 'C') {
            if (S.mode === 'qty') it.qty = 1;
            else if (S.mode === 'disc') it.disc = 0;
            else it.price = 0;
        } else if (k === 'del') {
            if (S.mode === 'qty') { var s = String(it.qty).slice(0, -1); it.qty = parseInt(s) || 1; }
            else if (S.mode === 'disc') { var s2 = String(it.disc).slice(0, -1); it.disc = parseFloat(s2) || 0; }
            else { var s3 = String(it.price).slice(0, -1); it.price = parseFloat(s3) || 0; }
        } else if (k.charAt(0) === '+') {
            var v = parseInt(k.slice(1));
            if (S.mode === 'qty') it.qty += v;
            else if (S.mode === 'price') it.price += v * 1000;
        } else {
            if (S.mode === 'qty') { it.qty = parseInt(String(it.qty) + k) || 1; }
            else if (S.mode === 'disc') { it.disc = Math.min(parseFloat(String(it.disc) + k) || 0, 100); }
            else { it.price = parseFloat(String(it.price) + k) || 0; }
        }
        if (it.qty <= 0) it.qty = 1;
        rCart();
    }

    function total() {
        var sum = 0;
        for (var i = 0; i < S.cart.length; i++) {
            sum += S.cart[i].price * S.cart[i].qty * (1 - S.cart[i].disc / 100);
        }
        return sum;
    }

    function goPayment() {
        if (!S.cart.length) return;
        var t = total();
        S.payInp = String(t);
        S.payFirst = true; // Flag for first digit replacement
        $('pay-big').textContent = vnd(t);
        $('ps-amt').textContent = vnd(t);
        var cnt = 0;
        for (var i = 0; i < S.cart.length; i++) cnt += S.cart[i].qty;
        $('ps-cnt').textContent = cnt;
        var ph = $('c-phone').value.trim(), nm = $('c-name').value.trim();
        $('pr-cust').textContent = ph ? (nm || 'Khach') + ' \u2014 ' + ph : 'Khach vang lai';
        var lhtml = '';
        for (var j = 0; j < S.cart.length; j++) {
            var it = S.cart[j];
            var itName = it.display_name || it.name || 'Sản phẩm';
            lhtml += '<div class="pr-line"><span>' + itName + ' \u00D7' + it.qty + '</span><span>' + vnd(it.price * it.qty * (1 - it.disc / 100)) + '</span></div>';
        }
        $('pr-lines').innerHTML = lhtml;
        show('s2');
    }

    function payM(el) {
        var ms = document.querySelectorAll('.pm');
        for (var i = 0; i < ms.length; i++) ms[i].classList.remove('on');
        el.classList.add('on');
        S.payMeth = el.getAttribute('data-m');
    }

    function pnp(k) {
        if (k === 'del') { 
            S.payInp = S.payInp.slice(0, -1) || '0'; 
            S.payFirst = false;
        }
        else if (k === 'pm') { 
            S.payInp = '0'; 
            S.payFirst = false;
        }
        else if (k.charAt(0) === '+') {
            var v = parseInt(k.slice(1));
            S.payInp = String((parseInt(S.payInp) || 0) + v * 1000);
            S.payFirst = false;
        }
        else {
            if (S.payFirst || S.payInp === '0') S.payInp = String(k);
            else S.payInp += String(k);
            S.payFirst = false;
        }
        $('pay-big').textContent = vnd(parseFloat(S.payInp) || 0);
        var t = total();
        var inp = parseFloat(S.payInp) || 0;
        var change = Math.max(0, inp - t);
        var changeEl = $('pay-change');
        if (changeEl) changeEl.textContent = vnd(change);
    }

    function confirm() {
        var btn = $('btn-cfm');
        btn.disabled = true;
        btn.textContent = 'Dang xu ly...';
        var lines = [];
        for (var i = 0; i < S.cart.length; i++) {
            var it = S.cart[i];
            lines.push({product_id: it.product_id, qty: it.qty, price: it.price * (1 - it.disc / 100)});
        }
        var orderData = {
            shift_id: S.sid,
            customer_phone: $('c-phone').value.trim(),
            customer_name: $('c-name').value.trim(),
            payment_method: S.payMeth,
            lines: lines
        };
        rpc('/bhx/pos/validate_order', {order_data: orderData}).then(function(r) {
            if (r && r.success) { okScreen(r.order_name); }
            else { alert('Loi: ' + (r ? r.error : 'Unknown')); }
        }).catch(function() {
            alert('Loi ket noi!');
        }).finally(function() {
            btn.disabled = false;
            btn.textContent = 'XAC NHAN THANH TOAN';
        });
    }

    function okScreen(name) {
        $('ok-order').textContent = 'Ma don: ' + name;
        $('rcpt-code').textContent = name;
        var now = new Date();
        $('rcpt-date').textContent = now.toLocaleDateString('vi-VN') + ' ' + now.toLocaleTimeString('vi-VN');
        var lhtml = '';
        var grandTotal = total();
        for (var i = 0; i < S.cart.length; i++) {
            var it = S.cart[i];
            var itName = it.display_name || it.name || 'Sản phẩm';
            lhtml += '<div class="rcpt-ln"><span>' + itName + ' \u00D7' + it.qty + '</span><span>' + vnd(it.price * it.qty * (1 - it.disc / 100)) + '</span></div>';
        }
        $('rcpt-lines').innerHTML = lhtml;
        $('rcpt-total').textContent = vnd(grandTotal);
        var mm = {cash: 'Tiền mặt', bank: 'Ngân hàng', card: 'Thẻ'};
        $('rcpt-meth').textContent = mm[S.payMeth] || 'Tiền mặt';
        
        // Lucky Spin Integration: Order >= 1,000,000 VND
        var spinBtn = $('btn-spin-lucky');
        if (spinBtn) {
            if (grandTotal >= 1000000) spinBtn.style.display = 'flex';
            else spinBtn.style.display = 'none';
        }

        // Update live cash balance if payment was cash
        if (S.payMeth === 'cash') {
            S.cashBal += grandTotal;
        }
        var cashEl = $('ok-cash');
        if (cashEl) cashEl.textContent = vnd(S.cashBal);
        
        show('s3');
    }

    function newOrder() {
        S.cart = []; S.selIdx = -1; S.payInp = ''; S.payMeth = 'cash';
        $('c-phone').value = ''; $('c-name').value = '';
        var ms = document.querySelectorAll('.pm');
        for (var i = 0; i < ms.length; i++) ms[i].classList.remove('on');
        var cashBtn = document.querySelector('.pm[data-m="cash"]');
        if (cashBtn) cashBtn.classList.add('on');
        var si = $('search');
        if (si) { si.value = ''; S.sq = ''; }
        rCart(); rProds(); show('s1');
    }

    function rpc(url, params) {
        return fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({jsonrpc: '2.0', method: 'call', id: 1, params: params})
        }).then(function(r) { return r.json(); }).then(function(d) { return d.result; });
    }

    function printReceipt() {
        window.print();
    }

    function goToSpin() {
        var name = $('c-name').value.trim();
        var phone = $('c-phone').value.trim();
        var url = '/lucky-spin';
        if (name || phone) {
            url += '?name=' + encodeURIComponent(name) + '&phone=' + encodeURIComponent(phone);
        }
        window.open(url, '_blank');
    }

    return {
        init: init, show: show, add: add, chg: chg, rm: rm, sel: sel,
        cat: cat, setMode: setMode, np: np, goPayment: goPayment,
        payM: payM, pnp: pnp, confirm: confirm, newOrder: newOrder,
        printReceipt: printReceipt, goToSpin: goToSpin
    };
})();

document.addEventListener('DOMContentLoaded', function() { P.init(); });
