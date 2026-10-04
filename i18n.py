"""FreshRoute interface translations (English and Urdu).

No Streamlit imports. Use tr(lang, key, **params) where lang is "en" or "ur".
Missing Urdu strings fall back to English, so the app never shows a blank.
"""

from __future__ import annotations

STRINGS = {
    "en": {
        # ---- general ----
        "hero_title": "🚚 FreshRoute",
        "hero_sub": "Get fresh produce to market faster, using trucks that are already heading your way.",
        "hint_voice": "You can speak or type in English, Urdu or Roman Urdu.",
        "language": "Language",
        "language_help": "Used for the app, voice input and written answers.",
        "tab_home": "🏠 Home",
        "tab_farmers": "🌾 Farmers",
        "tab_drivers": "🚚 Drivers",
        "tab_assistant": "💬 Assistant",
        "tab_about": "ℹ️ About",
        "sep": ", ",
        "row": "Row {n}",

        # ---- crops / vehicles / urgency ----
        "crop_tomato": "Tomato",
        "crop_mango": "Mango",
        "crop_banana": "Banana",
        "crop_strawberry": "Strawberry",
        "crop_spinach": "Spinach",
        "crop_potato": "Potato",
        "crop_onion": "Onion",
        "vehicle_refrigerated": "Refrigerated truck",
        "vehicle_covered": "Covered truck",
        "vehicle_open": "Open truck",
        "urgency_GREEN": "Green",
        "urgency_YELLOW": "Yellow",
        "urgency_ORANGE": "Orange",
        "urgency_RED": "Red",
        "urgency_text_GREEN": "Plenty of time",
        "urgency_text_YELLOW": "Move within a day",
        "urgency_text_ORANGE": "Move soon",
        "urgency_text_RED": "Critical, move immediately",

        # ---- fleet validation ----
        "err_id_required": "{where}: Truck ID is required.",
        "err_vehicle": "{where}: choose refrigerated, covered or open.",
        "err_capacity": "{where}: capacity must be greater than 0.",
        "err_free": "{where}: 'Free in (hours)' must be 0 or more.",
        "err_rating": "{where}: rating must be between 0 and 1.",
        "err_location": "{where}: current location is required.",
        "err_destination": "{where}: returning destination is required.",
        "err_phone": "{where}: the phone number does not look valid.",
        "err_duplicate": "Truck ID '{id}' is used more than once.",
        "truck_skipped": "{id} was skipped: {err}",

        # ---- voice ----
        "voice_record_first": "Please record a message first.",
        "voice_done": "Done. Check the text, then press the fill button.",
        "voice_fail": "We could not process the recording: {err}",
        "voice_no_text": "There is no text to read yet.",
        "voice_read_fail": "We could not read the text: {err}",
        "voice_filled": "Filled in: {fields}. Please review before {next}.",
        "voice_next_continue": "continuing",
        "voice_next_register": "registering",
        "voice_none_shipment": "We could not find shipment details in that message.",
        "voice_none_vehicle": "We could not find vehicle details in that message.",
        "voice_unavailable": "Voice input is not available right now. Please use the form below.",
        "voice_record": "Record your message",
        "voice_transcribe": "Convert recording to text",
        "voice_heard": "What we heard (you can edit it)",
        "voice_fill": "Fill the form from this text",
        "f_crop": "crop",
        "f_quantity": "quantity",
        "f_age": "time since harvest",
        "f_pickup": "pickup location",
        "f_destination": "destination",
        "f_name": "name",
        "f_phone": "phone",
        "f_vehicle": "vehicle type",
        "f_capacity": "capacity",
        "f_availability": "availability",
        "f_location": "current location",

        # ---- driver registration ----
        "fix_prefix": "Please fix: {errors}",
        "geo_fail": "We could not find your {label} ('{value}'). {err}",
        "label_current_location": "current location",
        "label_return_destination": "returning destination",
        "truck_registered": "{id} is registered. Farmers can now be matched with it.",

        # ---- analysis ----
        "enter_pickup": "Enter the pickup location.",
        "enter_delivery": "Enter the delivery location.",
        "no_trucks": "No trucks are registered yet. Add one in the Drivers tab.",
        "loc_not_found": "We could not find that location. {err}",
        "fix_fleet_first": "Please fix the truck list first: {errors}",
        "no_usable_trucks": "No usable trucks found. {warnings}",

        # ---- map ----
        "leg_truck_to_farm": "Truck to farm",
        "leg_farm_to_buyer": "Farm to buyer",
        "leg_buyer_to_dest": "Buyer to truck destination",
        "pt_farm": "Farm",
        "pt_buyer": "Buyer",
        "pt_truck": "Recommended truck",
        "map_caption": "Orange: truck to your farm. Green: farm to buyer. Grey: buyer to the truck's own destination.",

        # ---- results table ----
        "col_truck": "Truck",
        "col_driver": "Driver",
        "col_result": "Result",
        "col_score": "Match score",
        "col_extra": "Extra distance (km)",
        "col_to_farm": "Distance to farm (km)",
        "col_hours": "Hours to deliver",
        "col_fresh": "Freshness left (h)",
        "col_notes": "Notes",
        "suitable": "Suitable",
        "not_suitable": "Not suitable",
        "good_match": "Good match.",
        "rej_vehicle_unknown": "Unknown vehicle type '{vehicle}'.",
        "rej_vehicle_not_suitable": "A {vehicle} is not recommended for {crop}.",
        "rej_capacity_zero": "Truck capacity must be greater than zero.",
        "rej_capacity_low": "Truck capacity ({cap} kg) is below the shipment quantity ({qty} kg).",
        "rej_availability_invalid": "Driver availability time is invalid.",
        "rej_routing_unavailable": "Routing data is unavailable for this truck.",
        "rej_detour": "Extra distance is {detour} km, which exceeds the {limit} km limit.",
        "rej_shelf_below_min": "Remaining freshness is already below the safety buffer ({min} h).",
        "rej_shelf_after_delivery": "Delivery would leave only {left} h of freshness (minimum {min} h).",
        "rej_eval_error": "Could not evaluate this truck: {message}",

        # ---- results ----
        "your_results": "Your results",
        "stale_warning": "Your details or the truck list changed after this check. Press **Find trucks** again to refresh the results.",
        "weather_failed": "Live weather is unavailable, so the temperature you entered under Advanced options was used.",
        "road_fallback": "Live road data is temporarily unavailable, so some distances are approximate.",
        "m_temp": "Temperature at farm",
        "m_fresh_left": "Freshness left",
        "m_urgency": "Urgency",
        "m_suitable": "Suitable trucks",
        "fresh_caption": "{text}. Freshness is an estimate based on crop, time since harvest, condition and temperature.",
        "how_fresh": "How freshness was estimated",
        "how_fresh_text": "A {crop} normally stays fresh for about {base} hours. After {age} hours since harvest, today's heat and the produce condition, about {used} hours of that have been used.",
        "how_fresh_caption": "This is a planning estimate, not a food-safety guarantee. Refrigerated trucks are assumed to keep produce at its ideal temperature while loaded.",
        "recommended": "✅ Recommended: {id}",
        "m_score": "Match score",
        "m_extra": "Extra distance",
        "m_time": "Time to deliver",
        "m_fresh_at": "Freshness at delivery",
        "capacity_n": "capacity {n} kg",
        "driver_n": "driver {name}",
        "no_suitable": "No suitable truck was found right now. Try again later, or ask drivers to register more trucks in the Drivers tab.",
        "all_trucks": "All trucks compared",
        "download_csv": "Download comparison (CSV)",
        "summary_header": "Shipment summary",
        "summary_unavailable": "The written summary is not available right now.",
        "write_summary": "Write a shipment summary",
        "writing_summary": "Writing your summary...",
        "summary_fail": "We could not write the summary: {err}",
        "download_summary": "Download summary",
        "map_header": "Map",

        # ---- home ----
        "how_works": "How FreshRoute works",
        "step1_t": "Farmers describe their produce",
        "step1_d": "Say or type the crop, quantity and where it needs to go.",
        "step2_t": "Drivers register their truck",
        "step2_d": "Share the vehicle, free space and the route the truck is returning on.",
        "step3_t": "FreshRoute finds the best match",
        "step3_d": "We check space, extra distance and how fresh the produce will still be when it arrives.",
        "s_trucks": "Trucks registered",
        "s_fridge": "Refrigerated trucks",
        "s_crops": "Crops supported",
        "for_farmers": "🌾 For farmers",
        "for_farmers_d": "Find a truck for your harvest before it spoils. Open the **Farmers** tab to get started.",
        "for_drivers": "🚚 For drivers",
        "for_drivers_d": "Earn from empty return trips. Open the **Drivers** tab to register your truck.",

        # ---- farmers ----
        "farmer_header": "Find a truck for your produce",
        "farmer_intro": "Tell us about your harvest and where it needs to go.",
        "farmer_voice_title": "🎙️ Prefer to speak? Describe your shipment",
        "farmer_voice_hint": "Example: \"I have 800 kg of tomatoes harvested 6 hours ago in Bahawalpur. I need to send them to Multan.\"",
        "your_produce": "Your produce",
        "farmer_id": "Your name or ID",
        "crop": "Crop",
        "quantity": "Quantity (kg)",
        "harvest_age": "Hours since harvest",
        "condition": "Produce condition",
        "condition_help": "1.0 = excellent, 0.1 = badly deteriorated.",
        "pickup_delivery": "Pickup and delivery",
        "pickup_loc": "Pickup location (your farm)",
        "delivery_loc": "Delivery location (buyer)",
        "advanced": "Advanced options",
        "fallback_temp": "Temperature to use if live weather is unavailable (°C)",
        "find_trucks": "Find trucks",
        "looking": "Looking for the best truck for you...",

        # ---- drivers ----
        "driver_header": "Register your truck",
        "driver_intro": "Returning with an empty or half-empty truck? Tell us about your vehicle and route, and farmers can be matched with you.",
        "driver_voice_title": "🎙️ Prefer to speak? Describe your truck",
        "driver_voice_hint": "Example: \"My name is Ali, phone 0300 1234567. I have a covered truck with 4 tons capacity in Lodhran, returning to Bahawalpur, free in 2 hours.\"",
        "you_and_truck": "You and your truck",
        "your_name": "Your name",
        "your_phone": "Phone number (shown to the farmer you are matched with)",
        "truck_id": "Truck ID",
        "vehicle_type": "Vehicle type",
        "free_capacity": "Free capacity (kg)",
        "free_in": "Free in how many hours? (0 = free now)",
        "your_route": "Your route",
        "truck_now": "Where is the truck now?",
        "truck_returning": "Where is it returning to?",
        "register_truck": "Register truck",
        "registered_trucks": "Registered trucks",
        "ov_truck": "Truck",
        "ov_driver": "Driver",
        "ov_phone": "Phone",
        "ov_vehicle": "Vehicle",
        "ov_capacity": "Capacity (kg)",
        "ov_free": "Free in (h)",
        "ov_from": "From",
        "ov_to": "To",
        "edit_trucks": "Edit or remove trucks",
        "ed_truck_id": "Truck ID",
        "ed_driver": "Driver name",
        "ed_phone": "Phone",
        "ed_vehicle": "Vehicle",
        "ed_capacity": "Capacity (kg)",
        "ed_free": "Free in (h)",
        "ed_current": "Current location",
        "ed_returning": "Returning to",
        "ed_rating": "Rating (0-1)",
        "save_changes": "Save changes",
        "keep_one": "Keep at least one truck.",
        "changes_saved": "Changes saved.",
        "restore_sample": "Restore sample trucks",
        "rules_caption": "A truck is only matched if the extra distance is at most {km} km and the produce will still have at least {h} hours of freshness left on arrival.",

        # ---- assistant ----
        "assistant_header": "Ask FreshRoute",
        "assistant_need_result": "Find trucks for a shipment first, then ask questions about the result.",
        "assistant_unavailable": "The assistant is not available right now.",
        "current_shipment": "Current shipment: **{crop}, {qty} kg**",
        "assistant_try": "Try: Why was this truck chosen? What is the biggest risk? What should I do next?",
        "clear_chat": "Clear conversation",
        "chat_input": "Type your question",
        "thinking": "Thinking...",
        "answer_fail": "We could not answer that: {err}",

        # ---- about ----
        "about_header": "About FreshRoute",
        "about_md": """
### Why it exists

Farmers often struggle to find transport before their produce spoils, while
trucks returning from deliveries travel with empty space. FreshRoute connects
the two, so produce reaches buyers fresher and trucks earn from trips that
would otherwise be wasted.

### What we check for every truck

- The vehicle suits the crop (for example, strawberries need refrigeration)
- The truck has enough space and is free in time
- The extra distance to collect and deliver the produce is small
- The produce will still be fresh when it arrives

### Good to know

- Freshness is a planning estimate, not a food-safety guarantee.
- Distances are approximate because places are located by town or city.
- Trucks you register are kept only for your current visit. They are not
  stored permanently.
- FreshRoute is a prototype that supports decisions. Please confirm
  details directly with the driver or farmer before loading.
""",
    },
    "ur": {
        # ---- general ----
        "hero_title": "🚚 فریش روٹ",
        "hero_sub": "پہلے سے آپ کی طرف آنے والے ٹرکوں کے ذریعے تازہ پیداوار جلدی منڈی تک پہنچائیں۔",
        "hint_voice": "آپ انگریزی، اردو یا رومن اردو میں بول یا لکھ سکتے ہیں۔",
        "language": "زبان",
        "language_help": "ایپ، آواز کے ذریعے اندراج اور تحریری جوابات کے لیے۔",
        "tab_home": "🏠 ہوم",
        "tab_farmers": "🌾 کسان",
        "tab_drivers": "🚚 ڈرائیور",
        "tab_assistant": "💬 اسسٹنٹ",
        "tab_about": "ℹ️ تعارف",
        "sep": "، ",
        "row": "قطار {n}",

        # ---- crops / vehicles / urgency ----
        "crop_tomato": "ٹماٹر",
        "crop_mango": "آم",
        "crop_banana": "کیلا",
        "crop_strawberry": "اسٹرابیری",
        "crop_spinach": "پالک",
        "crop_potato": "آلو",
        "crop_onion": "پیاز",
        "vehicle_refrigerated": "ٹھنڈا (ریفریجریٹڈ) ٹرک",
        "vehicle_covered": "ڈھکا ہوا ٹرک",
        "vehicle_open": "کھلا ٹرک",
        "urgency_GREEN": "سبز",
        "urgency_YELLOW": "پیلا",
        "urgency_ORANGE": "نارنجی",
        "urgency_RED": "سرخ",
        "urgency_text_GREEN": "کافی وقت ہے",
        "urgency_text_YELLOW": "ایک دن کے اندر روانہ کریں",
        "urgency_text_ORANGE": "جلد روانہ کریں",
        "urgency_text_RED": "انتہائی نازک، فوراً روانہ کریں",

        # ---- fleet validation ----
        "err_id_required": "{where}: ٹرک آئی ڈی ضروری ہے۔",
        "err_vehicle": "{where}: ٹھنڈا، ڈھکا ہوا یا کھلا ٹرک منتخب کریں۔",
        "err_capacity": "{where}: گنجائش 0 سے زیادہ ہونی چاہیے۔",
        "err_free": "{where}: 'کتنے گھنٹے میں خالی' کی قدر 0 یا اس سے زیادہ ہونی چاہیے۔",
        "err_rating": "{where}: ریٹنگ 0 اور 1 کے درمیان ہونی چاہیے۔",
        "err_location": "{where}: موجودہ مقام ضروری ہے۔",
        "err_destination": "{where}: واپسی کی منزل ضروری ہے۔",
        "err_phone": "{where}: فون نمبر درست نہیں لگتا۔",
        "err_duplicate": "ٹرک آئی ڈی '{id}' ایک سے زیادہ بار استعمال ہوئی ہے۔",
        "truck_skipped": "{id} کو چھوڑ دیا گیا: {err}",

        # ---- voice ----
        "voice_record_first": "براہِ کرم پہلے پیغام ریکارڈ کریں۔",
        "voice_done": "مکمل۔ متن دیکھ لیں، پھر فارم بھرنے کا بٹن دبائیں۔",
        "voice_fail": "ہم ریکارڈنگ پر کارروائی نہیں کر سکے: {err}",
        "voice_no_text": "ابھی پڑھنے کے لیے کوئی متن موجود نہیں۔",
        "voice_read_fail": "ہم متن نہیں پڑھ سکے: {err}",
        "voice_filled": "یہ بھر دیا گیا: {fields}۔ {next} سے پہلے براہِ کرم جانچ لیں۔",
        "voice_next_continue": "آگے بڑھنے",
        "voice_next_register": "رجسٹر کرنے",
        "voice_none_shipment": "اس پیغام میں مال کی تفصیلات نہیں ملیں۔",
        "voice_none_vehicle": "اس پیغام میں گاڑی کی تفصیلات نہیں ملیں۔",
        "voice_unavailable": "آواز کے ذریعے اندراج ابھی دستیاب نہیں۔ براہِ کرم نیچے دیا گیا فارم استعمال کریں۔",
        "voice_record": "اپنا پیغام ریکارڈ کریں",
        "voice_transcribe": "ریکارڈنگ کو متن میں بدلیں",
        "voice_heard": "ہم نے جو سنا (آپ اسے ٹھیک کر سکتے ہیں)",
        "voice_fill": "اس متن سے فارم بھریں",
        "f_crop": "فصل",
        "f_quantity": "مقدار",
        "f_age": "کٹائی کے بعد کا وقت",
        "f_pickup": "اٹھانے کا مقام",
        "f_destination": "منزل",
        "f_name": "نام",
        "f_phone": "فون",
        "f_vehicle": "گاڑی کی قسم",
        "f_capacity": "گنجائش",
        "f_availability": "دستیابی",
        "f_location": "موجودہ مقام",

        # ---- driver registration ----
        "fix_prefix": "براہِ کرم درست کریں: {errors}",
        "geo_fail": "ہم آپ کا {label} ('{value}') نہیں ڈھونڈ سکے۔ {err}",
        "label_current_location": "موجودہ مقام",
        "label_return_destination": "واپسی کی منزل",
        "truck_registered": "{id} رجسٹر ہو گیا ہے۔ اب کسانوں کو اس کے ساتھ ملایا جا سکتا ہے۔",

        # ---- analysis ----
        "enter_pickup": "اٹھانے کا مقام درج کریں۔",
        "enter_delivery": "پہنچانے کا مقام درج کریں۔",
        "no_trucks": "ابھی کوئی ٹرک رجسٹر نہیں۔ ڈرائیور ٹیب میں ایک شامل کریں۔",
        "loc_not_found": "ہم وہ مقام نہیں ڈھونڈ سکے۔ {err}",
        "fix_fleet_first": "براہِ کرم پہلے ٹرکوں کی فہرست درست کریں: {errors}",
        "no_usable_trucks": "کوئی قابلِ استعمال ٹرک نہیں ملا۔ {warnings}",

        # ---- map ----
        "leg_truck_to_farm": "ٹرک سے کھیت تک",
        "leg_farm_to_buyer": "کھیت سے خریدار تک",
        "leg_buyer_to_dest": "خریدار سے ٹرک کی منزل تک",
        "pt_farm": "کھیت",
        "pt_buyer": "خریدار",
        "pt_truck": "تجویز کردہ ٹرک",
        "map_caption": "نارنجی: ٹرک سے آپ کے کھیت تک۔ سبز: کھیت سے خریدار تک۔ سرمئی: خریدار سے ٹرک کی اپنی منزل تک۔",

        # ---- results table ----
        "col_truck": "ٹرک",
        "col_driver": "ڈرائیور",
        "col_result": "نتیجہ",
        "col_score": "میچ اسکور",
        "col_extra": "اضافی فاصلہ (کلومیٹر)",
        "col_to_farm": "کھیت تک فاصلہ (کلومیٹر)",
        "col_hours": "پہنچانے کے گھنٹے",
        "col_fresh": "باقی تازگی (گھنٹے)",
        "col_notes": "نوٹ",
        "suitable": "موزوں",
        "not_suitable": "موزوں نہیں",
        "good_match": "اچھا میچ۔",
        "rej_vehicle_unknown": "گاڑی کی قسم '{vehicle}' نامعلوم ہے۔",
        "rej_vehicle_not_suitable": "{crop} کے لیے {vehicle} تجویز نہیں کی جاتی۔",
        "rej_capacity_zero": "ٹرک کی گنجائش صفر سے زیادہ ہونی چاہیے۔",
        "rej_capacity_low": "ٹرک کی گنجائش ({cap} کلو) مال کی مقدار ({qty} کلو) سے کم ہے۔",
        "rej_availability_invalid": "ڈرائیور کی دستیابی کا وقت درست نہیں۔",
        "rej_routing_unavailable": "اس ٹرک کے لیے راستے کا ڈیٹا دستیاب نہیں۔",
        "rej_detour": "اضافی فاصلہ {detour} کلومیٹر ہے جو {limit} کلومیٹر کی حد سے زیادہ ہے۔",
        "rej_shelf_below_min": "باقی تازگی پہلے ہی حفاظتی حد ({min} گھنٹے) سے کم ہے۔",
        "rej_shelf_after_delivery": "پہنچنے پر صرف {left} گھنٹے کی تازگی بچے گی (کم از کم {min} گھنٹے درکار)۔",
        "rej_eval_error": "اس ٹرک کا جائزہ نہیں لیا جا سکا: {message}",

        # ---- results ----
        "your_results": "آپ کے نتائج",
        "stale_warning": "اس جانچ کے بعد آپ کی تفصیلات یا ٹرکوں کی فہرست بدل گئی ہے۔ نتائج تازہ کرنے کے لیے دوبارہ **ٹرک تلاش کریں** دبائیں۔",
        "weather_failed": "براہِ راست موسم کی معلومات دستیاب نہیں، اس لیے 'اضافی آپشنز' میں درج کیا گیا درجہ حرارت استعمال ہوا۔",
        "road_fallback": "سڑک کا براہِ راست ڈیٹا عارضی طور پر دستیاب نہیں، اس لیے کچھ فاصلے اندازاً ہیں۔",
        "m_temp": "کھیت پر درجہ حرارت",
        "m_fresh_left": "باقی تازگی",
        "m_urgency": "ہنگامی کیفیت",
        "m_suitable": "موزوں ٹرک",
        "fresh_caption": "{text}۔ تازگی کا اندازہ فصل، کٹائی کے بعد کے وقت، حالت اور درجہ حرارت پر مبنی ہے۔",
        "how_fresh": "تازگی کا اندازہ کیسے لگایا گیا",
        "how_fresh_text": "{crop} عام طور پر تقریباً {base} گھنٹے تازہ رہتا ہے۔ کٹائی کے {age} گھنٹے بعد، آج کی گرمی اور پیداوار کی حالت کو مدنظر رکھیں تو اس میں سے تقریباً {used} گھنٹے خرچ ہو چکے ہیں۔",
        "how_fresh_caption": "یہ منصوبہ بندی کا اندازہ ہے، خوراک کی حفاظت کی ضمانت نہیں۔ فرض کیا گیا ہے کہ ٹھنڈے ٹرک لوڈ کے دوران پیداوار کو مثالی درجہ حرارت پر رکھتے ہیں۔",
        "recommended": "✅ تجویز کردہ: {id}",
        "m_score": "میچ اسکور",
        "m_extra": "اضافی فاصلہ",
        "m_time": "پہنچانے کا وقت",
        "m_fresh_at": "پہنچنے پر تازگی",
        "capacity_n": "گنجائش {n} کلو",
        "driver_n": "ڈرائیور {name}",
        "no_suitable": "فی الحال کوئی موزوں ٹرک نہیں ملا۔ بعد میں دوبارہ کوشش کریں، یا ڈرائیوروں سے کہیں کہ ڈرائیور ٹیب میں مزید ٹرک رجسٹر کریں۔",
        "all_trucks": "تمام ٹرکوں کا موازنہ",
        "download_csv": "موازنہ ڈاؤن لوڈ کریں (CSV)",
        "summary_header": "مال کا خلاصہ",
        "summary_unavailable": "تحریری خلاصہ ابھی دستیاب نہیں۔",
        "write_summary": "مال کا خلاصہ لکھیں",
        "writing_summary": "آپ کا خلاصہ لکھا جا رہا ہے...",
        "summary_fail": "ہم خلاصہ نہیں لکھ سکے: {err}",
        "download_summary": "خلاصہ ڈاؤن لوڈ کریں",
        "map_header": "نقشہ",

        # ---- home ----
        "how_works": "فریش روٹ کیسے کام کرتا ہے",
        "step1_t": "کسان اپنی پیداوار بیان کرتے ہیں",
        "step1_d": "فصل، مقدار اور منزل بول کر یا لکھ کر بتائیں۔",
        "step2_t": "ڈرائیور اپنا ٹرک رجسٹر کرتے ہیں",
        "step2_d": "گاڑی، خالی جگہ اور واپسی کا راستہ بتائیں۔",
        "step3_t": "فریش روٹ بہترین میچ ڈھونڈتا ہے",
        "step3_d": "ہم جگہ، اضافی فاصلہ اور پہنچنے پر پیداوار کی تازگی جانچتے ہیں۔",
        "s_trucks": "رجسٹرڈ ٹرک",
        "s_fridge": "ٹھنڈے ٹرک",
        "s_crops": "معاون فصلیں",
        "for_farmers": "🌾 کسانوں کے لیے",
        "for_farmers_d": "فصل خراب ہونے سے پہلے اس کے لیے ٹرک تلاش کریں۔ شروع کرنے کے لیے **کسان** ٹیب کھولیں۔",
        "for_drivers": "🚚 ڈرائیوروں کے لیے",
        "for_drivers_d": "خالی واپسی کے سفر سے کمائیں۔ اپنا ٹرک رجسٹر کرنے کے لیے **ڈرائیور** ٹیب کھولیں۔",

        # ---- farmers ----
        "farmer_header": "اپنی پیداوار کے لیے ٹرک تلاش کریں",
        "farmer_intro": "ہمیں اپنی فصل اور اس کی منزل کے بارے میں بتائیں۔",
        "farmer_voice_title": "🎙️ بولنا پسند ہے؟ اپنا مال بیان کریں",
        "farmer_voice_hint": "مثال: \"میرے پاس بہاولپور میں 6 گھنٹے پہلے توڑے گئے 800 کلو ٹماٹر ہیں۔ مجھے انہیں ملتان بھیجنا ہے۔\"",
        "your_produce": "آپ کی پیداوار",
        "farmer_id": "آپ کا نام یا آئی ڈی",
        "crop": "فصل",
        "quantity": "مقدار (کلو)",
        "harvest_age": "کٹائی کو کتنے گھنٹے ہوئے",
        "condition": "پیداوار کی حالت",
        "condition_help": "1.0 = بہترین، 0.1 = بہت خراب۔",
        "pickup_delivery": "اٹھانے اور پہنچانے کا مقام",
        "pickup_loc": "اٹھانے کا مقام (آپ کا کھیت)",
        "delivery_loc": "پہنچانے کا مقام (خریدار)",
        "advanced": "اضافی آپشنز",
        "fallback_temp": "براہِ راست موسم دستیاب نہ ہو تو استعمال ہونے والا درجہ حرارت (°C)",
        "find_trucks": "ٹرک تلاش کریں",
        "looking": "آپ کے لیے بہترین ٹرک تلاش کیا جا رہا ہے...",

        # ---- drivers ----
        "driver_header": "اپنا ٹرک رجسٹر کریں",
        "driver_intro": "خالی یا آدھے خالی ٹرک کے ساتھ واپس جا رہے ہیں؟ ہمیں اپنی گاڑی اور راستے کے بارے میں بتائیں، کسانوں کو آپ کے ساتھ ملایا جا سکے گا۔",
        "driver_voice_title": "🎙️ بولنا پسند ہے؟ اپنا ٹرک بیان کریں",
        "driver_voice_hint": "مثال: \"میرا نام علی ہے، فون 0300 1234567۔ میرے پاس 4 ٹن گنجائش کا ڈھکا ہوا ٹرک ہے، میں لودھراں میں ہوں، بہاولپور واپس جا رہا ہوں، 2 گھنٹے میں خالی ہوں گا۔\"",
        "you_and_truck": "آپ اور آپ کا ٹرک",
        "your_name": "آپ کا نام",
        "your_phone": "فون نمبر (جس کسان سے ملایا جائے اسے دکھایا جائے گا)",
        "truck_id": "ٹرک آئی ڈی",
        "vehicle_type": "گاڑی کی قسم",
        "free_capacity": "خالی گنجائش (کلو)",
        "free_in": "کتنے گھنٹے میں خالی ہوں گے؟ (0 = ابھی خالی)",
        "your_route": "آپ کا راستہ",
        "truck_now": "ٹرک اس وقت کہاں ہے؟",
        "truck_returning": "ٹرک کہاں واپس جا رہا ہے؟",
        "register_truck": "ٹرک رجسٹر کریں",
        "registered_trucks": "رجسٹرڈ ٹرک",
        "ov_truck": "ٹرک",
        "ov_driver": "ڈرائیور",
        "ov_phone": "فون",
        "ov_vehicle": "گاڑی",
        "ov_capacity": "گنجائش (کلو)",
        "ov_free": "خالی ہونے میں (گھنٹے)",
        "ov_from": "از",
        "ov_to": "تک",
        "edit_trucks": "ٹرک میں ترمیم کریں یا ہٹائیں",
        "ed_truck_id": "ٹرک آئی ڈی",
        "ed_driver": "ڈرائیور کا نام",
        "ed_phone": "فون",
        "ed_vehicle": "گاڑی",
        "ed_capacity": "گنجائش (کلو)",
        "ed_free": "خالی ہونے میں (گھنٹے)",
        "ed_current": "موجودہ مقام",
        "ed_returning": "واپسی کی منزل",
        "ed_rating": "ریٹنگ (0-1)",
        "save_changes": "تبدیلیاں محفوظ کریں",
        "keep_one": "کم از کم ایک ٹرک رکھیں۔",
        "changes_saved": "تبدیلیاں محفوظ ہو گئیں۔",
        "restore_sample": "نمونے کے ٹرک بحال کریں",
        "rules_caption": "ٹرک کو صرف اسی صورت میں میچ کیا جاتا ہے جب اضافی فاصلہ زیادہ سے زیادہ {km} کلومیٹر ہو اور پہنچنے پر پیداوار میں کم از کم {h} گھنٹے کی تازگی باقی ہو۔",

        # ---- assistant ----
        "assistant_header": "فریش روٹ سے پوچھیں",
        "assistant_need_result": "پہلے کسی مال کے لیے ٹرک تلاش کریں، پھر نتیجے کے بارے میں سوال پوچھیں۔",
        "assistant_unavailable": "اسسٹنٹ ابھی دستیاب نہیں۔",
        "current_shipment": "موجودہ مال: **{crop}، {qty} کلو**",
        "assistant_try": "آزمائیں: یہ ٹرک کیوں منتخب ہوا؟ سب سے بڑا خطرہ کیا ہے؟ مجھے آگے کیا کرنا چاہیے؟",
        "clear_chat": "گفتگو صاف کریں",
        "chat_input": "اپنا سوال لکھیں",
        "thinking": "سوچ رہا ہوں...",
        "answer_fail": "ہم اس کا جواب نہیں دے سکے: {err}",

        # ---- about ----
        "about_header": "فریش روٹ کے بارے میں",
        "about_md": """
### یہ کیوں بنایا گیا

کسان اکثر پیداوار خراب ہونے سے پہلے ٹرانسپورٹ ڈھونڈنے میں مشکل کا شکار ہوتے ہیں،
جبکہ ڈیلیوری سے واپس آنے والے ٹرک خالی جگہ کے ساتھ سفر کرتے ہیں۔ فریش روٹ ان
دونوں کو ملاتا ہے، تاکہ پیداوار خریداروں تک زیادہ تازہ پہنچے اور ٹرک ان سفروں سے
کمائیں جو ورنہ ضائع ہو جاتے۔

### ہر ٹرک کے لیے ہم کیا جانچتے ہیں

- گاڑی فصل کے لیے موزوں ہے (مثلاً اسٹرابیری کے لیے ٹھنڈا ٹرک ضروری ہے)
- ٹرک میں کافی جگہ ہے اور وہ وقت پر خالی ہے
- پیداوار اٹھانے اور پہنچانے کے لیے اضافی فاصلہ کم ہے
- پہنچنے پر پیداوار ابھی تازہ ہوگی

### جاننا ضروری ہے

- تازگی منصوبہ بندی کا اندازہ ہے، خوراک کی حفاظت کی ضمانت نہیں۔
- فاصلے اندازاً ہیں کیونکہ مقامات کو شہر یا قصبے کے مرکز سے تلاش کیا جاتا ہے۔
- آپ کے رجسٹر کیے ہوئے ٹرک صرف آپ کے موجودہ وزٹ تک محفوظ رہتے ہیں۔ انہیں
  مستقل طور پر محفوظ نہیں کیا جاتا۔
- فریش روٹ ایک پروٹوٹائپ ہے جو فیصلوں میں مدد دیتا ہے۔ براہِ کرم لوڈ کرنے سے پہلے
  ڈرائیور یا کسان سے براہِ راست تفصیلات کی تصدیق کر لیں۔
""",
    },
}


def tr(lang: str, key: str, **params) -> str:
    """Look up a string; fall back to English, then to the key itself."""
    table = STRINGS.get(lang, STRINGS["en"])
    text = table.get(key)
    if text is None:
        text = STRINGS["en"].get(key, key)
    return text.format(**params) if params else text
