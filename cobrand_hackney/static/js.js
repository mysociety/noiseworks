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

})();
