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

function show_hide_checkbox(input, show_when_checked, ids) {
    var input = document.querySelector(`input[type='checkbox'][name='${input}']`);
    if (!input) {
        return;
    }
    let f = function() {
        let show = (input.checked && show_when_checked) || (!input.checked && !show_when_checked);
        show_hide_toggle(show, ids)
    };
    input.addEventListener('change', f);
    f();
}

show_hide("kind", "other", ["div_id_kind_other"]);
show_hide("kind-kind", "other", ["div_id_kind-kind_other"]);
show_hide("user_pick-user", "0", ['div_id_user_pick-first_name', 'div_id_user_pick-last_name', 'div_id_user_pick-email', 'div_id_user_pick-phone', 'div_id_user_pick-postcode']);
show_hide("user", "0", ['div_id_first_name', 'div_id_last_name', 'div_id_email', 'div_id_phone', 'div_id_address']);
show_hide("address-address_uprn", "missing", ["div_id_address-address_manual"]);
show_hide("user_address-address_uprn", "missing", ["div_id_user_address-address_manual"]);
show_hide_checkbox("in_the_past", true, ["div_id_date", "div_id_action_time"]);

construct_case_locations_dropdown();
update_case_listing_on_change();
expand_all_toggle();

})();

// ---

// Ajax updating of listing

function disable_searching() {
    var searchButton = document.querySelector('#cases-search-button');
    var loadingSpinner = document.querySelector('#loading-spinner');
    if (loadingSpinner) {
        loadingSpinner.style.display = "";
    }
    if (searchButton) {
        searchButton.disabled = true;
    }
}

function enable_searching() {
    var searchButton = document.querySelector('#cases-search-button');
    var loadingSpinner = document.querySelector('#loading-spinner');
    if (loadingSpinner) {
        loadingSpinner.style.display = "none";
    }
    if (searchButton) {
        searchButton.disabled = false;
    }
}

let controller;

function filter_update(e) {
    e.preventDefault();
    disable_searching();
    if (controller) {
        controller.abort();
    }
    var qs = new URLSearchParams(new FormData(this)).toString();
    var url = '/cases?ajax=1&' + qs;
    controller = new AbortController();
    fetch(url, { signal: controller.signal }).then(res => {
        enable_searching();
        if (!res.ok) {
            location.href = url;
        }
        return res.text();
    }).then(text => {
        document.querySelector('.js-case-list').innerHTML = text;
    }).catch(err => {
        if (err.name === 'AbortError') {
        } else {
            location.href = '/cases?' + qs;
        }
    });
}

function update_case_listing_on_change() {
    var form = document.querySelector('.case-filters form');
    if (!form) {
        return;
    }
    if (('fetch' in window) && ('FormData' in window) && ('URLSearchParams' in window)) {
        form.addEventListener('change', filter_update);
        form.addEventListener('submit', filter_update);
        document.querySelector('.case-filters input[type=submit]').style.display = "none";
    }
}

// Case locations dropdown

function same_contents(a, b) {
    var checked_values = [];
    a.forEach(function(i) { checked_values.push(i.value); });
    checked_values.sort();
    var user_wards = [];
    b.forEach(function(i) { user_wards.push(i); });
    user_wards.sort();
    for (var i=0; i<checked_values.length; i++) {
        if (checked_values[i] !== user_wards[i]) {
            return false;
        }
    }
    return true;
}

function construct_case_locations_dropdown() {
    var inputs = document.querySelectorAll('.govuk-checkboxes__input[name=ward][type=checkbox]');
    if (!inputs.length) {
        return;
    }

    var my_cases_option = '';
    if (nw.user_wards && nw.user_wards.length) {
        var area_names = [];
        for (var i = 0; i < inputs.length; i++) {
            if (nw.user_wards.indexOf(inputs[i].value) > -1) {
                var label = document.querySelector('label[for=' + inputs[i].id + ']');
                area_names.push(label.innerText);
            }
        }
        area_names = area_names.join(', ');
        var area_label = 'My wards';
        if (area_names) {
            area_label += ' (' + area_names + ')';
        }
        my_cases_option = '<option value="my_areas">' + area_label + '</option>';
    }
    var caseLocationDiv = document.createElement('div');
    caseLocationDiv.className = 'govuk-form-group lbh-form-group';
    caseLocationDiv.id = 'div_id_case_location';

    var extra_options = [];
    var extra_options_text = '';
    for (var i = 0; i < inputs.length; i++) {
        var val = inputs[i].value;
        if (!val.match(/[EWSN]\d{8}/)) {
            var label = document.querySelector('label[for=' + inputs[i].id + ']');
            extra_options_text += '<option value="' + val + '">' + label.innerText + '</option>';
            extra_options.push(val);
        }
    }

    caseLocationDiv.innerHTML = '<label for="id_case_location" class="govuk-label lbh-label">Case location</label>' + '<select class="govuk-select lbh-select" id="id_case_location"> <option value="all_areas" selected>All wards</option>' + my_cases_option + '<option value="selected_areas">Selected wards</option>' + extra_options_text + ' </select> ';

    // Defining the div that contains all the ward checkboxes
    var area = document.getElementById("div_id_ward");

    // Locating "Case Locations" before the area
    parentFormNode = area.parentNode;
    parentFormNode.insertBefore(caseLocationDiv, area);

    // Defining the rest of the variables
    var inputArea = document.getElementById("id_case_location");
    var myAreasCheckboxChecked = document.querySelectorAll('.govuk-checkboxes__input:checked');
    var myAreasCheckbox = document.querySelectorAll('.govuk-checkboxes__input');
    area.style.display = "none";

    // Whenever there is at least one checkbox checked the filter will select by default "selected areas"
    // and will display all the checkboxes.
    var found = false;
    for (var i=0; i<extra_options.length; i++) {
        if (document.querySelector('input[name="ward"][value="' + extra_options[i] + '"]').checked == true && myAreasCheckboxChecked.length == 1) {
            inputArea.value = extra_options[i];
            found = true;
        }
    }

    if (myAreasCheckboxChecked.length == myAreasCheckbox.length || myAreasCheckboxChecked.length == 0 ) {
        inputArea.value = 'all_areas';
    } else if (myAreasCheckboxChecked.length == nw.user_wards.length && same_contents(myAreasCheckboxChecked, nw.user_wards)) {
        inputArea.value = 'my_areas';
    } else if (!found) {
        inputArea.value = 'selected_areas';
        area.style.display = "block";
    }

    inputArea.addEventListener('change',function(){
        area.style.display = "none";
        if (inputArea.value == 'all_areas') {
            // all the checkboxes for areas will be clicked
            for (var i = 0; i < inputs.length; i++) {
                inputs[i].checked = false;
            }
        } else if (inputArea.value == 'selected_areas') {
            // selected areas. The checkboxes will become unchecked
            for (var i = 0; i < inputs.length; i++) {
                inputs[i].checked = false;
            }
            area.style.display = "block";
        } else if (inputArea.value == 'my_areas') {
            for (var i = 0; i < inputs.length; i++) {
                var my_area = nw.user_wards.indexOf(inputs[i].value) > -1;
                inputs[i].checked = my_area;
            }
        } else {
            // Special e.g. outside, north/south
            for (var i = 0; i < inputs.length; i++) {
                inputs[i].checked = false;
            }
            document.querySelector('input[name="ward"][value="' + inputArea.value + '"]').checked = true;
        }
    });
}

function expand_all_toggle() {
    var toggle = document.querySelector('#js-expand-toggle');
    toggle && toggle.addEventListener('click', function(e) {
        e.preventDefault();
        var expand;
        if (e.target.innerText === "Expand all") {
            e.target.innerText = "Collapse all";
            expand = true;
        } else {
            e.target.innerText = "Expand all";
            expand = false;
        }
        var details = document.querySelectorAll('details');
        [].forEach.call(details, function(obj, idx) {
            obj.open = expand;
        });
    });
}
