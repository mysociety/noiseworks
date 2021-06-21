// A minimized version of this is inline in the header.

(function(D){
    var E = D.documentElement;
    E.className = E.className.replace(/\bno-js\b/, 'js');
	var type = Modernizr.mq('(min-width: 48em)') ? 'desktop' : 'mobile';
    if ('IntersectionObserver' in window) {
		E.className += ' lazyload';
    }
    if (type == 'mobile') {
		E.className += ' mobile';
	}
})(document);
