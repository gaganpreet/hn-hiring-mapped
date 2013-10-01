/*jshint bitwise:false */
(function() {
    "use strict";
    var default_filters = {
        "h1b": "any",
        "intern": "any",
        "remote": "any",
        "location": "any",
        "stale": "any",
        "location_filter": "",
        "text_filter": ""
    };

    var all_posts;
    var filters = default_filters; // Stores the currently applied filters
    var view_type = "map"; // Current view type - map or list
    var map, iw, oms, bounds;
    map = iw = oms = bounds = undefined;

    var fetchData = function (month) {
        /* Fetch data for a given month
         * month should be of the form 'yyyy-mm'
         * Assign result to global variable all_posts
         */
        if (month === undefined) {
            month = available_data[available_data.length - 1];
        }
        $.getJSON(
            'data/' + month + '.json',
            function (data) {
                all_posts = data;
                $.each(all_posts, function(index, post) { 
                    post.full_text = post.full_html.replace(/(<.*?>)+/g, ' ');
                });
                showData();
            }
        );
    };

    var appendToList = function (html) {
        /* Append some html to the list view
         */
        $(html).appendTo('#jobs');
    };

    var addToMap = function (location_, type_of_post, post_html, post) {
        /* Add a marker to the map
         */
        var latLng = new google.maps.LatLng(post.lat, post.lon);
        bounds.extend(latLng);

        var marker = new google.maps.Marker({
            position: latLng,
            map: map,
            title: location_ + ' ' + type_of_post
        });

        marker.desc = '<div style="max-height: 300px;">' + post_html + '</div>';
        oms.addMarker(marker);
    };

    var showData = function () {
        $('#jobs').empty();
        $('#map-canvas').remove();
        var count = 0;

        if (view_type === "map") {
            initMap();
        }

        $.each(all_posts, function (index, post) {
            if (!doesMatchFilters(post)) {
                return true;
            }
            var type_of_post = '';
            if (post.h1b) {
                type_of_post += 'H-1B/';
            }
            if (post.remote) {
                type_of_post += 'Remote/';
            }
            if (post.intern) {
                type_of_post += 'Intern';
            }

            if (type_of_post[type_of_post.length - 1] === '/') {
                type_of_post = type_of_post.slice(0, -1);
            }

            var post_html = highlightSearchTerms(post.full_html, filters.text_filter);

            var location_ = post.address || 'None';

            var view = {'location': location_,
                        'type_of_post': type_of_post,
                        'link': post.url,
                        'user': post.user,
                        'post_html': post_html
                        };

            var template = ['<div class="post">',
                            '<h3>{{location}}</h3>',
                            '<h4>{{type_of_post}}</h4>',
                            '<a href="{{link}}">link</a>',
                            '// Posted by <a href="https://news.ycombinator.com/user?id={{user}}">{{user}}</a>',
                            '<p>{{{ post_html }}}</p>'].join('\n');

            var html = Mustache.render(template, view);

            if (view_type === "map") {
                addToMap(location_, type_of_post, html, post);
            }
            else {
                appendToList(html);
            }
            count += 1;

        });
        if (view_type === "map") {
            map.fitBounds(bounds);
        }
        var status_html = Mustache.render("<p>Displaying {{ count }} posts</p>", {"count": count});
        $('#status').html(status_html);
    };

    var highlightSearchTerms = function (text, filter) {
        /*
         * Highlight the `filter' in `text'
         * Regex courtesy: http://pureform.wordpress.com/2008/01/04/matching-a-word-characters-outside-of-html-tags/
         */
        if (filter) {
            var re = new RegExp('(' + filter + ')(?!([^<]+)?>)', 'ig');
            if (re.exec(text)) {
                text = text.replace(re, '<span class="highlight">$1</span>');
            }
        }
        return text;
    };

    var doesMatchFilters = function (item) {
        /* Match and return a boolean value 
         * if a job post matches the current filters
         */
        var match = true;

        var isBoolMatch = function (value, bool_type) {
            if (bool_type === "no") {
                return !value;
            }
            else if (bool_type === "yes") {
                return value;
            }
            else {
                return true;
            }
        };

        match &= isBoolMatch(item.h1b, filters.h1b);

        match &= isBoolMatch(item.intern, filters.intern);

        match &= isBoolMatch(item.remote, filters.remote);

        match &= isBoolMatch(!item.freshness, filters.stale);

        var location_available = item.address ? true : false;
        match &= isBoolMatch(location_available, filters.location);

        var text = item.full_text;
        var location_ = item.address;
        var re;
        if (filters.location_filter) {
            re = new RegExp(filters.location_filter, 'i');
            if (!re.exec(location_)) {
                match = false;
            }
        }

        if (filters.text_filter) {
            re = new RegExp(filters.text_filter, 'i');
            if (!re.exec(text)) {
                match = false;
            }
        }

        return match;
    };

    // Store any existing timeout ID to clear if needed for type ahead search
    var timeout = null;
    var updateFilters = function (o) {
        /* Triggered by event
         * Updates the filters array to the latest selection/input
         */
        if (filters[o.target.id] !== o.target.value) {
            clearTimeout(timeout);
            filters[o.target.id] = o.target.value;
            timeout = setTimeout(showData, 300);
        }
    };

    var showViewToggle = function () {
        /*
         * Show switch view text and add event listener
         */
        var template = "<p><a href='#' id='toggle_view'>View as {{ type }}</a></p>";
        var new_type = view_type === "map" ? "list" : "map";

        $('#view_type').html(Mustache.render(template, {"type": new_type}));
        $('#toggle_view').on('click', function () {
            view_type = view_type === "map" ? "list" : "map";
            showViewToggle();
            showData();
            e.preventDefault();
        });
    };

    var showMonthList = function () {
        /*
         * Show month list in the left column
         */
        $.each(available_data.reverse(), function (index, value) {
            var months = ['January', 'February', 'March', 'April', 
                          'May', 'June', 'July', 'August', 'September', 
                          'October', 'November', 'December'];
            
            var valueArray = value.split('-');

            var year = parseInt(valueArray[0], 10);
            var month = parseInt(valueArray[1], 10) - 1; 
            var month_name = months[month];

            var name = month_name + ' ' + year;
            
            $('<a>',{
                text: name,
                href: '#',
                class: 'month_selector'
            }).data('data-file', value).appendTo('#month_list');
            $('<br />').appendTo('#month_list');
        });
        $(".month_selector").on('click', function (event) {
            fetchData($.data(event.target, 'data-file'));
        });
    };


    var initUI = function () {
        $(":input").change(updateFilters);
        $(":input").on("input", null, null, updateFilters);
        showViewToggle();
        fetchData();
        showMonthList();
    };

    var initMap = function () { 
        /*
         * Initialize a map, an infowindow, spiderify and a bounds object
         */
        $('<div id="map-canvas">').appendTo("#view");
        var center = new google.maps.LatLng(0, 0);
        var mapOptions = {
            center: center,
            mapTypeId: google.maps.MapTypeId.ROADMAP
        };
        map = new google.maps.Map(document.getElementById('map-canvas'), mapOptions);
        iw = new google.maps.InfoWindow();
        bounds = new google.maps.LatLngBounds();

        oms = initOMS(iw);
    };

    var initOMS = function (iw) {
        /*
         * Initialize OverlappingMarkerSpiderfier so we have an easier way to browse posts
         * with same coordinates
         */
        var usualColor = 'eebb22';
        var spiderfiedColor = 'ffee22';
        var iconWithColor = function (color) {
            return 'http://chart.googleapis.com/chart?chst=d_map_xpin_letter&chld=pin|+|' +
                color + '|000000|ffff00';
        };
        var shadow = new google.maps.MarkerImage(
                'https://www.google.com/intl/en_ALL/mapfiles/shadow50.png',
                new google.maps.Size(37, 34),  // size   - for sprite clipping
                new google.maps.Point(0, 0),   // origin - ditto
                new google.maps.Point(10, 34)  // anchor - where to meet map location
                );

        oms = new OverlappingMarkerSpiderfier(map,
                {markersWontMove: true, markersWontHide: true, keepSpiderfied: true});

        oms.addListener('click', function (marker) {
            iw.setContent(marker.desc);
            iw.open(map, marker);
        });
        oms.addListener('spiderfy', function (markers) {
            for(var i = 0; i < markers.length; i ++) {
                markers[i].setIcon(iconWithColor(spiderfiedColor));
                markers[i].setShadow(null);
            } 
            iw.close();
        });
        oms.addListener('unspiderfy', function (markers) {
            for(var i = 0; i < markers.length; i ++) {
                markers[i].setIcon(iconWithColor(usualColor));
                markers[i].setShadow(shadow);
            }
        });

        return oms;
    };

    initUI();
})();
