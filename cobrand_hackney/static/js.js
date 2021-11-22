(function(){

function close_overlay() {
    var overlay = document.querySelector('.case-detail__map__overlay');
    overlay.style.display = 'none';
    focusLock.off(overlay);
}

// On first open it moves the map inside the overlay. This does mean if you use
// the overlay, then reisze your browser to desktop, you can't get the map
// anymore as there's no button either, but that seems unlikely.
document.querySelectorAll('.case-detail__map__button a').forEach(function(a) {
    a.addEventListener('click', function(e) {
        e.preventDefault();
        var map = document.querySelector('.case-detail__map');
        var overlay = document.querySelector('.case-detail__map__overlay');
        var contents = document.querySelector('.nw-dialog__contents');
        contents.insertAdjacentElement('afterbegin', map);
        overlay.style.display = 'block';
        map.style.display = 'block';
        nw.map.invalidateSize();
        focusLock.on(overlay);
    });
});

document.querySelectorAll('.lbh-dialog__close').forEach(function(b) {
    b.addEventListener('click', close_overlay);
});

/* Catch clicks on the faded out overlay itself */
document.querySelectorAll('.case-detail__map__overlay').forEach(function(b) {
    b.addEventListener('click', function(e) {
        if (e.target === e.currentTarget) {
            close_overlay();
        }
    });
});

/* Generic script for handling show-this-or-not-if-this-selected */

function show_hide_toggle(b, ids) {
    b = b ? 'block' : 'none';
    ids.forEach(function(el) {
        document.getElementById(el).style.display = b;
    });
}
function show_hide(input, value, ids) {
    var inputs = document.querySelectorAll('input[name="' + input + '"]');
    inputs.forEach(function(i) {
        i.addEventListener('change', function(e) {
            if (e.currentTarget.value == value) {
                show_hide_toggle(true, ids);
            } else {
                show_hide_toggle(false, ids);
            }
        });
    });
    if (inputs.length) {
        var el = document.querySelector('input[name="' + input + '"]:checked');
        if (el) {
            el.dispatchEvent(new Event('change'));
        } else {
            show_hide_toggle(false, ids);
        }
    }
}

show_hide("kind", "other", ["div_id_kind_other"]);
show_hide("user_pick-user", "0", ['div_id_user_pick-first_name', 'div_id_user_pick-last_name', 'div_id_user_pick-email', 'div_id_user_pick-phone', 'div_id_user_pick-address']);

})();
