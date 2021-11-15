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
show_hide("kind-kind", "other", ["div_id_kind-kind_other"]);
show_hide("where-where", "residence", ["div_id_where-estate"]);
show_hide("user_pick-user", "0", ['div_id_user_pick-first_name', 'div_id_user_pick-last_name', 'div_id_user_pick-email', 'div_id_user_pick-phone', 'div_id_user_pick-address']);

// Creating a new dropdown "Case Locations"
construct_case_locations_dropdown();

})();

// ---

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

    var my_cases_option = '';
    if (nw.user_wards.length) {
        var area_names = [];
        for (var i = 0; i < inputs.length; i++) {
            if (nw.user_wards.indexOf(inputs[i].value) > -1) {
                var label = document.querySelector('label[for=' + inputs[i].id + ']');
                area_names.push(label.innerText);
            }
        }
        area_names = area_names.join(', ');
        var area_label = 'My areas';
        if (area_names) {
            area_label += ' (' + area_names + ')';
        }
        my_cases_option = '<option value="my_areas">' + area_label + '</option>';
    }
    var caseLocationDiv = document.createElement('div');
    caseLocationDiv.className = 'govuk-form-group lbh-form-group';
    caseLocationDiv.id = 'div_id_case_location';
    caseLocationDiv.innerHTML = '<label for="id_case_location" class="govuk-label lbh-label">Case location</label>' + '<select class="govuk-select lbh-select" id="id_case_location"> <option value="all_areas" selected>All areas</option>' + my_cases_option + '<option value="selected_areas">Selected areas</option> <option value="outside_hackney">Outside Hackney</option> </select> ';

    // Defining the div that contains all the ward checkboxes
    var area = document.getElementById("div_id_ward");

    // Locating "Case Locations" before the area
    parentFormNode = area.parentNode;
    parentFormNode.insertBefore(caseLocationDiv, area);

    // Defining the rest of the variables
    var inputArea = document.getElementById("id_case_location");
    var outsideHackney = document.querySelector('input[name="ward"][value="outside"]');
    var myAreasCheckboxChecked = document.querySelectorAll('.govuk-checkboxes__input:checked');
    var myAreasCheckbox = document.querySelectorAll('.govuk-checkboxes__input');
    area.style.display = "none";

    // Whenever there is at least one checkbox checked the filter will select by default "selected areas"
    // and will display all the checkboxes.
    if (outsideHackney.checked == true && myAreasCheckboxChecked.length == 1) {
        inputArea.value = 'outside_hackney';
    } else if (myAreasCheckboxChecked.length == myAreasCheckbox.length || myAreasCheckboxChecked.length == 0 ) {
        inputArea.value = 'all_areas';
    } else if (myAreasCheckboxChecked.length == nw.user_wards.length && same_contents(myAreasCheckboxChecked, nw.user_wards)) {
        inputArea.value = 'my_areas';
    } else {
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
        } else if (inputArea.value =="outside_hackney") {
            // Outside hackney
            for (var i = 0; i < inputs.length; i++) {
                inputs[i].checked = false;
            }
            outsideHackney.checked = true;
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
        }
    });
}
