/* 
 * Lucky Spin - Bách Hóa Xanh
 * Runs when page is loaded, reads LUCKY_SPIN_PRIZES and LUCKY_SPIN_CAMPAIGN_ID from global scope
 */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var canvas = document.getElementById('luckyWheelCanvas');
        if (!canvas) return;

        var ctx = canvas.getContext('2d');
        var prizes = window.LUCKY_SPIN_PRIZES || [];
        var campaignId = window.LUCKY_SPIN_CAMPAIGN_ID || 0;
        var numSegments = prizes.length;
        var centerX = canvas.width / 2;
        var centerY = canvas.height / 2;
        var radius = canvas.width / 2 - 2;
        var currentDeg = 0; // Accumulated degrees for CSS transform

        var fallbackColors = ['#007b3e', '#fcdb04', '#1a9e5c', '#e0a800', '#00a854', '#ffc107', '#005f30', '#ff9800'];

        // ---- Draw Wheel ----
        function drawWheel() {
            if (numSegments === 0) {
                ctx.fillStyle = '#ccc';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                return;
            }
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            var anglePerSegment = (2 * Math.PI) / numSegments;

            for (var i = 0; i < numSegments; i++) {
                var prize = prizes[i];
                var startAngle = i * anglePerSegment - Math.PI / 2;
                var endAngle = startAngle + anglePerSegment;

                // Slice fill
                ctx.beginPath();
                ctx.moveTo(centerX, centerY);
                ctx.arc(centerX, centerY, radius, startAngle, endAngle);
                ctx.closePath();
                ctx.fillStyle = prize.color || fallbackColors[i % fallbackColors.length];
                ctx.fill();
                ctx.strokeStyle = '#fff';
                ctx.lineWidth = 2;
                ctx.stroke();

                // Slice text
                ctx.save();
                ctx.translate(centerX, centerY);
                ctx.rotate(startAngle + anglePerSegment / 2);
                ctx.textAlign = 'right';
                ctx.font = 'bold 16px Open Sans, Arial, sans-serif';
                var bgColor = prize.color || fallbackColors[i % fallbackColors.length];
                ctx.fillStyle = getContrastColor(bgColor);
                var text = prize.name || '';
                if (text.length > 18) text = text.substring(0, 15) + '...';
                ctx.fillText(text, radius - 15, 6);
                ctx.restore();
            }

            // Center circle
            ctx.beginPath();
            ctx.arc(centerX, centerY, 22, 0, 2 * Math.PI);
            ctx.fillStyle = '#fff';
            ctx.fill();
            ctx.strokeStyle = '#007b3e';
            ctx.lineWidth = 3;
            ctx.stroke();
        }

        function getContrastColor(hex) {
            if (!hex || hex.length < 4) return '#fff';
            hex = hex.replace('#', '');
            if (hex.length === 3) hex = hex[0] + hex[0] + hex[1] + hex[1] + hex[2] + hex[2];
            var r = parseInt(hex.substr(0, 2), 16);
            var g = parseInt(hex.substr(2, 2), 16);
            var b = parseInt(hex.substr(4, 2), 16);
            return ((r * 299 + g * 587 + b * 114) / 1000 >= 128) ? '#333' : '#fff';
        }

        drawWheel();

        // ---- Spin Button ----
        var btnSpin = document.getElementById('btn-spin');
        var resultMsg = document.getElementById('result-message');
        var spinning = false;

        btnSpin.addEventListener('click', function () {
            if (spinning) return;

            var name = document.getElementById('customer_name').value.trim();
            var phone = document.getElementById('customer_phone').value.trim();

            if (!name || !phone) {
                showResult('alert-warning', '⚠️ Vui lòng nhập đầy đủ Họ Tên và Số Điện Thoại!');
                return;
            }

            spinning = true;
            btnSpin.disabled = true;
            btnSpin.textContent = 'ĐANG QUAY...';
            resultMsg.classList.add('d-none');

            // Call backend API
            fetch('/web/dataset/call_kw', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        model: 'bhx_lucky_spin.history',
                        method: 'search_read',
                        args: [],
                        kwargs: {}
                    }
                })
            });

            // Use our JSON RPC route
            fetch('/lucky-spin/play', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    id: 1,
                    method: 'call',
                    params: {
                        name: name,
                        phone: phone,
                        campaign_id: campaignId
                    }
                })
            })
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    var result = data.result || {};
                    if (data.error || result.error) {
                        var errMsg = (data.error && data.error.data && data.error.data.message) || result.error || 'Lỗi không xác định';
                        showResult('alert-danger', '❌ ' + errMsg);
                        spinning = false;
                        btnSpin.disabled = false;
                        btnSpin.textContent = 'QUAY NGAY! 🎰';
                        return;
                    }

                    // Find which segment to stop at
                    var winPrizeId = result.prize_id;
                    var winIndex = prizes.findIndex(function (p) { return p.id === winPrizeId; });

                    var degreesPerSegment = 360 / numSegments;
                    var extraSpins = 5; // 5 full rounds
                    var targetAngle;

                    if (winIndex >= 0) {
                        // Center of winning segment from the top (angle 0)
                        var segmentCenterAngle = winIndex * degreesPerSegment + degreesPerSegment / 2;
                        // We want segment center to point to the TOP (where pointer is)
                        // So we rotate until segmentCenterAngle is at 0 (top)
                        var rotateExtra = (360 - segmentCenterAngle % 360);
                        // Small random jitter inside the slice so wheel doesn't stop exactly at center every time
                        var jitter = (Math.random() - 0.5) * degreesPerSegment * 0.6;
                        targetAngle = (extraSpins * 360) + rotateExtra + jitter;
                    } else {
                        targetAngle = (extraSpins * 360) + Math.random() * 360;
                    }

                    currentDeg += targetAngle;

                    // Apply spin via CSS transition
                    canvas.style.transition = 'transform 5s cubic-bezier(0.17, 0.67, 0.12, 0.99)';
                    canvas.style.transform = 'rotate(' + currentDeg + 'deg)';

                    setTimeout(function () {
                        spinning = false;
                        btnSpin.disabled = false;
                        btnSpin.textContent = 'QUAY LẠI! 🎰';
                        canvas.style.transition = '';

                        if (result.prize_id) {
                            showResult('alert-success', '🎉 ' + result.message);
                        } else {
                            showResult('alert-info', '😊 ' + result.message);
                        }
                    }, 5200);
                })
                .catch(function (err) {
                    console.error('Error:', err);
                    showResult('alert-danger', '❌ Có lỗi xảy ra, vui lòng thử lại sau.');
                    spinning = false;
                    btnSpin.disabled = false;
                    btnSpin.textContent = 'QUAY NGAY! 🎰';
                });
        });

        function showResult(className, message) {
            resultMsg.className = 'alert mt-4 text-center ' + className;
            resultMsg.innerHTML = '<strong>' + message + '</strong>';
        }
    });
})();
