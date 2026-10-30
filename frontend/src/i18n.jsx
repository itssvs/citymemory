// Language (English / Tamil) and text size, remembered per browser.
// Tamil covers the citizen screens, login, navigation and footer; staff screens are English.
import { createContext, useContext, useEffect, useState } from 'react'

const load = (k, d) => { try { return localStorage.getItem(k) || d } catch { return d } }
const save = (k, v) => { try { localStorage.setItem(k, v) } catch { /* storage blocked */ } }

export const SIZES = { small: 14, normal: 15, large: 17 }

const EN = {
  corp: 'Demo Municipal Corporation',
  service: 'CityMemory: civic infrastructure history',
  ward: 'Ward 12',
  skip: 'Skip to main content',
  textSize: 'Text size',
  smaller: 'Smaller text', normalText: 'Normal text', larger: 'Larger text',
  language: 'Language',
  logout: 'Log out',
  welcome: 'Welcome, {name}',
  role_citizen: 'Citizen', role_engineer: 'Ward engineer', role_commissioner: 'Commissioner',
  // nav
  nav_home: 'Home', nav_report: 'Report a problem', nav_mine: 'My reports',
  nav_today: 'Today', nav_jobs: 'Repair jobs', nav_map: 'Ward map', nav_review: 'Review queue', nav_patterns: 'Patterns',
  nav_overview: 'Overview', nav_assets: 'Assets', nav_contractors: 'Contractors', nav_prediction: 'Prediction check',
  ai_on: 'AI services on', ai_part: 'AI services partly on', ai_off: 'AI services off',
  // footer
  privacy: 'Privacy notice', accessibility: 'Accessibility statement', help: 'Help',
  updated: 'Data last updated', prototype: 'Prototype with simulated data. Not an official government service.',
  close: 'Close',
  // citizen
  cit_sub: 'Report a broken road, drain or light, and follow it until it is fixed.',
  yourReports: 'Your reports', total: '{n} reports in total',
  st_fixed: 'Fixed', st_repairing: 'Being repaired', st_review: 'Under review',
  st_fixed_note: 'repair finished', st_repairing_note: 'waiting for or under repair', st_review_note: 'being checked by an engineer',
  latest: 'Latest updates', latestSub: 'Each report is linked to the road, drain or light it is about.', seeAll: 'See all {n}',
  mineSub: 'Newest first. Only you can see your reports.',
  none: 'You have not reported anything yet. Use Report a problem to add your first one.',
  target: 'Target date for the repair',
  others: '{n} other reports about this spot.',
  failedN: 'It has failed {n} times, so the city treats it as a recurring problem.',
  yourPhoto: 'Your photo', afterPhoto: 'After the repair',
  reportedOn: 'reported {d}',
  calTitle: 'Your reports by day', today: 'Today', repairDone: 'Repair done', filed: 'Complaints filed',
  calTotals: '{c} complaints, {r} repairs',
  // statuses and steps
  'Fixed': 'Fixed', 'Work started': 'Work started', 'Repair assigned': 'Repair assigned',
  'Waiting for repair': 'Waiting for repair', 'Under review': 'Under review',
  step_submitted: 'Submitted', step_linked: "Linked to the asset's history", step_checking: 'Being checked by an engineer',
  step_assigned: 'Repair assigned', step_assigned_to: 'Repair assigned to {c}', step_started: 'Work started',
  step_fixed: 'Fixed', step_fixed_permanent: 'Fixed permanently', step_fixed_temporary: 'Fixed with a temporary repair',
  // report form
  rf_title: 'Report a problem', rf_sub: 'We check its history before anything else.',
  rf_what: 'What is the problem with?', rf_describe: 'Describe it',
  rf_placeholder: 'For example: big pothole near the bus stop, water stays after rain',
  rf_photo: 'Add a photo (optional)', rf_pin: 'Pin placed on the map', rf_nopin: 'No pin yet',
  rf_tap: 'Tap the map where the problem is', rf_circles: 'Circles show locations already on record.',
  rf_submit: 'Submit report', rf_checking: 'Checking history…',
  rf_needPin: 'Tap the map to place a pin where the problem is.',
  rf_needConsent: 'Please read the privacy notice and tick the box to continue.',
  rf_tooBig: 'That photo is larger than {n} MB. Please choose a smaller one.',
  rf_ref: 'Reference number', rf_track: 'Track it in My reports', rf_answered: 'Answered in {ms} ms.',
  res_auto: 'This spot is already on record', res_review: 'This may be a known problem. An engineer will confirm.',
  res_new_asset: 'New problem registered', res_duplicate: 'You already reported this',
  yourPin: 'Your pin', known: 'Known location', bigger: 'Bigger circle means more failures',
  road: 'Road', drain: 'Drain', streetlight: 'Streetlight', footpath: 'Footpath', toilet: 'Public toilet',
  // privacy notice
  pn_title: 'Privacy notice',
  pn_what: 'What we collect', pn_what_a: 'Your description of the problem, the location you pin on the map, a photo if you add one, and your account name.',
  pn_why: 'Why we collect it', pn_why_a: 'To find the problem, link it to earlier reports about the same road, drain or light, and get it repaired.',
  pn_who: 'Who can see it', pn_who_a: 'Ward engineers and officials of the corporation. Your photo is never published, and the hidden location and phone details inside the photo are removed when you upload it.',
  pn_long: 'How long we keep it', pn_long_a: 'As part of the repair history of that asset, so the city can see what keeps failing.',
  pn_choice: 'Your choices', pn_choice_a: 'You can ask the ward office to show you, correct or delete your personal details.',
  pn_agree: 'I have read this notice and agree to my report being used to fix the problem.',
  // login
  lg_title: 'Log in', lg_register: 'Create a citizen account', lg_name: 'Your name', lg_user: 'Username', lg_pass: 'Password',
  lg_wait: 'One moment…', lg_create: 'Create account', lg_new: 'New here?', lg_staff: 'Staff accounts are issued by the corporation.',
  lg_have: 'Already registered?',
  lg_head: 'Every complaint and repair, linked to the road, drain or light it is about.',
  lg_lead: 'So the same pothole is not treated as a new problem every month.',
  lg_how: 'How it works',
  lg_s1: 'You report a problem with a pin and a photo.', lg_s2: 'It is linked to everything reported about that spot before.',
  lg_s3: 'Engineers fix what fails most, and you can follow it until it is fixed.',
  demo: 'Demo access', demoSub: 'For evaluation only. Each role opens its own dashboard with simulated data.', open: 'Open',
  demo_citizen: 'Report problems, track your reports', demo_engineer: 'What to fix first, and repair jobs', demo_commissioner: 'Spend and stop-patching decisions',
  total1: '1 report in total', others1: '1 other report about this spot.',
  res_title_review: 'Possible match. An engineer will confirm.',
  res_msg_auto: 'This spot is already on record. Your report has been added to its history.',
  res_msg_review: 'This may be a problem that was reported before. An engineer will check and confirm.',
  res_msg_new_asset: 'Registered as a new problem. An engineer will verify it.',
  res_msg_duplicate: 'You reported this recently, so we kept your earlier report.',
  menu: 'Menu',
  acc_title: 'Accessibility statement',
  acc_items: [
    'This prototype aims to meet WCAG 2.1 level AA, the standard adopted by the Guidelines for Indian Government Websites (GIGW 3.0).',
    'Every page can be used with a keyboard. Use the "Skip to main content" link at the top to go straight to the page content.',
    'Use A−, A and A+ at the top of the page to change the text size. Your choice is remembered on this browser.',
    'Citizen screens, login, navigation and this footer are available in Tamil. Staff dashboards are in English only for now.',
    'Text and buttons are checked for colour contrast of at least 4.5 to 1.',
    'Known limitation: the map needs a mouse or touch. Every map item is also listed in text on the same page.',
    'If something does not work for you, tell the ward office and we will fix it.',
  ],
  help_title: 'Help',
  help_items: [
    ['How do I report a problem?', 'Open Report a problem, choose what is broken, describe it, tap the map where it is, and submit. A photo helps but is optional.'],
    ['What happens next?', 'Your report is linked to everything reported about that spot before. An engineer reviews it and assigns a repair.'],
    ['How do I track it?', 'Open My reports. Each report shows its steps: submitted, linked, repair assigned, work started and fixed, with a target date.'],
    ['Why does it say "already on record"?', 'Someone has reported the same spot before. Your report is added to that history, which helps the city see it keeps failing.'],
    ['Who do I contact?', 'This is a prototype. In a real service, the ward office contact details would be shown here.'],
  ],
}

const TA = {
  corp: 'மாதிரி மாநகராட்சி',
  service: 'சிட்டிமெமரி: குடிமை உள்கட்டமைப்பு வரலாறு',
  ward: 'வார்டு 12',
  skip: 'முதன்மை உள்ளடக்கத்திற்குச் செல்லவும்',
  textSize: 'எழுத்து அளவு',
  smaller: 'சிறிய எழுத்து', normalText: 'இயல்பான எழுத்து', larger: 'பெரிய எழுத்து',
  language: 'மொழி',
  logout: 'வெளியேறு',
  welcome: 'வணக்கம், {name}',
  role_citizen: 'குடிமகன்', role_engineer: 'வார்டு பொறியாளர்', role_commissioner: 'ஆணையர்',
  nav_home: 'முகப்பு', nav_report: 'புகார் அளிக்க', nav_mine: 'எனது புகார்கள்',
  nav_today: 'இன்று', nav_jobs: 'பழுது நீக்கப் பணிகள்', nav_map: 'வார்டு வரைபடம்', nav_review: 'சரிபார்ப்பு வரிசை', nav_patterns: 'தொடர் பிரச்சினைகள்',
  nav_overview: 'கண்ணோட்டம்', nav_assets: 'சொத்துக்கள்', nav_contractors: 'ஒப்பந்ததாரர்கள்', nav_prediction: 'கணிப்புச் சோதனை',
  ai_on: 'AI சேவைகள் இயங்குகின்றன', ai_part: 'AI சேவைகள் பகுதியளவு இயங்குகின்றன', ai_off: 'AI சேவைகள் இயங்கவில்லை',
  privacy: 'தனியுரிமை அறிவிப்பு', accessibility: 'அணுகல்தன்மை அறிக்கை', help: 'உதவி',
  updated: 'தரவு கடைசியாகப் புதுப்பிக்கப்பட்டது', prototype: 'இது மாதிரித் தரவுடன் கூடிய முன்மாதிரி. அதிகாரப்பூர்வ அரசு சேவை அல்ல.',
  close: 'மூடு',
  cit_sub: 'பழுதான சாலை, வடிகால் அல்லது தெருவிளக்கைப் புகாரளித்து, அது சரிசெய்யப்படும் வரை கண்காணிக்கவும்.',
  yourReports: 'உங்கள் புகார்கள்', total: 'மொத்தம் {n} புகார்கள்',
  st_fixed: 'சரிசெய்யப்பட்டது', st_repairing: 'பழுது நீக்கத்தில்', st_review: 'பரிசீலனையில்',
  st_fixed_note: 'பழுது நீக்கம் முடிந்தது', st_repairing_note: 'பழுது நீக்கக் காத்திருக்கிறது அல்லது நடைபெறுகிறது', st_review_note: 'பொறியாளர் சரிபார்க்கிறார்',
  latest: 'சமீபத்திய நிலவரம்', latestSub: 'ஒவ்வொரு புகாரும் தொடர்புடைய சாலை, வடிகால் அல்லது விளக்குடன் இணைக்கப்படுகிறது.', seeAll: 'அனைத்து {n} புகார்களையும் பார்க்க',
  mineSub: 'புதியவை முதலில். உங்கள் புகார்களை நீங்கள் மட்டுமே பார்க்க முடியும்.',
  none: 'நீங்கள் இன்னும் எதையும் புகாரளிக்கவில்லை. முதல் புகாரை அளிக்க "புகார் அளிக்க" என்பதைப் பயன்படுத்தவும்.',
  target: 'பழுது நீக்க இலக்குத் தேதி',
  others: 'இந்த இடம் குறித்து மேலும் {n} புகார்கள் உள்ளன.',
  failedN: 'இது {n} முறை பழுதடைந்துள்ளது; எனவே மாநகராட்சி இதை மீண்டும் மீண்டும் வரும் பிரச்சினையாகக் கருதுகிறது.',
  yourPhoto: 'உங்கள் புகைப்படம்', afterPhoto: 'பழுது நீக்கிய பின்',
  reportedOn: '{d} அன்று புகாரளிக்கப்பட்டது',
  calTitle: 'நாள் வாரியாக உங்கள் புகார்கள்', today: 'இன்று', repairDone: 'பழுது நீக்கப்பட்டது', filed: 'புகார்கள் பதிவாகின',
  calTotals: '{c} புகார்கள், {r} பழுது நீக்கங்கள்',
  'Fixed': 'சரிசெய்யப்பட்டது', 'Work started': 'பணி தொடங்கியது', 'Repair assigned': 'பழுது நீக்கப் பணி ஒதுக்கப்பட்டது',
  'Waiting for repair': 'பழுது நீக்கக் காத்திருக்கிறது', 'Under review': 'பரிசீலனையில்',
  step_submitted: 'சமர்ப்பிக்கப்பட்டது', step_linked: 'முந்தைய பதிவுகளுடன் இணைக்கப்பட்டது', step_checking: 'பொறியாளர் சரிபார்க்கிறார்',
  step_assigned: 'பழுது நீக்கப் பணி ஒதுக்கப்பட்டது', step_assigned_to: '{c} அவர்களுக்குப் பணி ஒதுக்கப்பட்டது', step_started: 'பணி தொடங்கியது',
  step_fixed: 'சரிசெய்யப்பட்டது', step_fixed_permanent: 'நிரந்தரமாகச் சரிசெய்யப்பட்டது', step_fixed_temporary: 'தற்காலிகமாகச் சரிசெய்யப்பட்டது',
  rf_title: 'புகார் அளிக்க', rf_sub: 'முதலில் இதன் முந்தைய வரலாற்றைச் சரிபார்க்கிறோம்.',
  rf_what: 'எதில் பிரச்சினை?', rf_describe: 'விவரிக்கவும்',
  rf_placeholder: 'எ.கா: பேருந்து நிறுத்தம் அருகே பெரிய குழி, மழைக்குப் பின் தண்ணீர் தேங்குகிறது',
  rf_photo: 'புகைப்படம் சேர்க்கவும் (விருப்பத்தேர்வு)', rf_pin: 'வரைபடத்தில் இடம் குறிக்கப்பட்டது', rf_nopin: 'இன்னும் இடம் குறிக்கப்படவில்லை',
  rf_tap: 'பிரச்சினை உள்ள இடத்தை வரைபடத்தில் தொடவும்', rf_circles: 'வட்டங்கள் ஏற்கனவே பதிவில் உள்ள இடங்களைக் காட்டுகின்றன.',
  rf_submit: 'புகாரைச் சமர்ப்பிக்கவும்', rf_checking: 'வரலாற்றைச் சரிபார்க்கிறது…',
  rf_needPin: 'பிரச்சினை உள்ள இடத்தைக் குறிக்க வரைபடத்தைத் தொடவும்.',
  rf_needConsent: 'தொடர, தனியுரிமை அறிவிப்பைப் படித்துப் பெட்டியைத் தேர்வு செய்யவும்.',
  rf_tooBig: 'இந்தப் புகைப்படம் {n} MB-ஐ விடப் பெரியது. சிறிய புகைப்படத்தைத் தேர்வு செய்யவும்.',
  rf_ref: 'குறிப்பு எண்', rf_track: 'எனது புகார்களில் கண்காணிக்கவும்', rf_answered: '{ms} மி.வி.யில் பதிலளிக்கப்பட்டது.',
  res_auto: 'இந்த இடம் ஏற்கனவே பதிவில் உள்ளது', res_review: 'இது முன்பே பதிவான பிரச்சினையாக இருக்கலாம். பொறியாளர் உறுதிசெய்வார்.',
  res_new_asset: 'புதிய பிரச்சினை பதிவு செய்யப்பட்டது', res_duplicate: 'இதை நீங்கள் ஏற்கனவே புகாரளித்துள்ளீர்கள்',
  yourPin: 'நீங்கள் குறித்த இடம்', known: 'பதிவில் உள்ள இடம்', bigger: 'பெரிய வட்டம் = அதிக முறை பழுது',
  road: 'சாலை', drain: 'வடிகால்', streetlight: 'தெருவிளக்கு', footpath: 'நடைபாதை', toilet: 'பொதுக் கழிப்பிடம்',
  pn_title: 'தனியுரிமை அறிவிப்பு',
  pn_what: 'நாங்கள் சேகரிப்பவை', pn_what_a: 'பிரச்சினை பற்றிய உங்கள் விவரம், வரைபடத்தில் நீங்கள் குறிக்கும் இடம், நீங்கள் சேர்த்தால் புகைப்படம், உங்கள் கணக்குப் பெயர்.',
  pn_why: 'ஏன் சேகரிக்கிறோம்', pn_why_a: 'பிரச்சினையைக் கண்டறிந்து, அதே சாலை, வடிகால் அல்லது விளக்கு பற்றிய முந்தைய புகார்களுடன் இணைத்து, பழுது நீக்க.',
  pn_who: 'யார் பார்க்க முடியும்', pn_who_a: 'வார்டு பொறியாளர்களும் மாநகராட்சி அலுவலர்களும் மட்டும். உங்கள் புகைப்படம் வெளியிடப்படாது; பதிவேற்றும்போது அதிலுள்ள மறைந்த இருப்பிட, கைபேசி விவரங்கள் நீக்கப்படும்.',
  pn_long: 'எவ்வளவு காலம் வைத்திருப்போம்', pn_long_a: 'அந்தச் சொத்தின் பழுது நீக்க வரலாற்றின் ஒரு பகுதியாக, எது மீண்டும் மீண்டும் பழுதடைகிறது என்பதை மாநகராட்சி அறிய.',
  pn_choice: 'உங்கள் தேர்வுகள்', pn_choice_a: 'உங்கள் தனிப்பட்ட விவரங்களைப் பார்க்க, திருத்த அல்லது நீக்க வார்டு அலுவலகத்திடம் கேட்கலாம்.',
  pn_agree: 'இந்த அறிவிப்பைப் படித்தேன்; பிரச்சினையைச் சரிசெய்ய என் புகாரைப் பயன்படுத்த ஒப்புக்கொள்கிறேன்.',
  lg_title: 'உள்நுழைக', lg_register: 'குடிமக்கள் கணக்கைத் தொடங்கவும்', lg_name: 'உங்கள் பெயர்', lg_user: 'பயனர் பெயர்', lg_pass: 'கடவுச்சொல்',
  lg_wait: 'சற்றுப் பொறுக்கவும்…', lg_create: 'கணக்கைத் தொடங்கு', lg_new: 'புதியவரா?', lg_staff: 'பணியாளர் கணக்குகளை மாநகராட்சி வழங்குகிறது.',
  lg_have: 'ஏற்கனவே பதிவு செய்துள்ளீர்களா?',
  lg_head: 'ஒவ்வொரு புகாரும் பழுது நீக்கமும், அது தொடர்புடைய சாலை, வடிகால் அல்லது விளக்குடன் இணைக்கப்படுகிறது.',
  lg_lead: 'அதனால் ஒரே குழி ஒவ்வொரு மாதமும் புதிய பிரச்சினையாகக் கருதப்படாது.',
  lg_how: 'இது எப்படிச் செயல்படுகிறது',
  lg_s1: 'இடத்தைக் குறித்து, புகைப்படத்துடன் புகார் அளிக்கிறீர்கள்.', lg_s2: 'அந்த இடம் குறித்து முன்பு வந்த எல்லாப் புகார்களுடனும் அது இணைக்கப்படுகிறது.',
  lg_s3: 'அதிகம் பழுதடைவதைப் பொறியாளர்கள் முதலில் சரிசெய்கிறார்கள்; சரியாகும் வரை நீங்கள் கண்காணிக்கலாம்.',
  demo: 'மாதிரி அணுகல்', demoSub: 'மதிப்பீட்டிற்கு மட்டும். ஒவ்வொரு பங்கும் மாதிரித் தரவுடன் தனி டாஷ்போர்டைத் திறக்கும்.', open: 'திற',
  demo_citizen: 'புகார் அளித்து, கண்காணிக்க', demo_engineer: 'முதலில் சரிசெய்ய வேண்டியவை, பழுது நீக்கப் பணிகள்', demo_commissioner: 'செலவு, நிரந்தரத் தீர்வு முடிவுகள்',
  total1: 'மொத்தம் 1 புகார்', others1: 'இந்த இடம் குறித்து மேலும் 1 புகார் உள்ளது.',
  res_title_review: 'முன்பே பதிவானதாக இருக்கலாம். பொறியாளர் உறுதிசெய்வார்.',
  res_msg_auto: 'இந்த இடம் ஏற்கனவே பதிவில் உள்ளது. உங்கள் புகார் அதன் வரலாற்றில் சேர்க்கப்பட்டது.',
  res_msg_review: 'இது முன்பே புகாரளிக்கப்பட்ட பிரச்சினையாக இருக்கலாம். பொறியாளர் சரிபார்த்து உறுதிசெய்வார்.',
  res_msg_new_asset: 'புதிய பிரச்சினையாகப் பதிவு செய்யப்பட்டது. பொறியாளர் இதைச் சரிபார்ப்பார்.',
  res_msg_duplicate: 'இதை நீங்கள் சமீபத்தில் புகாரளித்துள்ளீர்கள்; உங்கள் முந்தைய புகார் வைத்துக்கொள்ளப்பட்டது.',
  menu: 'பட்டியல்',
  acc_title: 'அணுகல்தன்மை அறிக்கை',
  acc_items: [
    'இந்த முன்மாதிரி, இந்திய அரசு இணையதள வழிகாட்டுதல்கள் (GIGW 3.0) ஏற்றுக்கொண்ட WCAG 2.1 AA தரத்தை அடைய முயல்கிறது.',
    'ஒவ்வொரு பக்கத்தையும் விசைப்பலகை மூலம் பயன்படுத்தலாம். நேரடியாகப் பக்க உள்ளடக்கத்திற்குச் செல்ல மேலே உள்ள "முதன்மை உள்ளடக்கத்திற்குச் செல்லவும்" இணைப்பைப் பயன்படுத்தவும்.',
    'எழுத்து அளவை மாற்ற மேலே உள்ள A−, A, A+ ஐப் பயன்படுத்தவும். உங்கள் தேர்வு இந்த உலாவியில் நினைவில் வைக்கப்படும்.',
    'குடிமக்கள் திரைகள், உள்நுழைவு, வழிசெலுத்தல், இந்த அடிக்குறிப்பு ஆகியவை தமிழில் உள்ளன. பணியாளர் டாஷ்போர்டுகள் தற்போது ஆங்கிலத்தில் மட்டும்.',
    'எழுத்துகளும் பொத்தான்களும் குறைந்தது 4.5:1 வண்ண மாறுபாட்டிற்குச் சரிபார்க்கப்பட்டுள்ளன.',
    'அறியப்பட்ட வரம்பு: வரைபடத்திற்கு மவுஸ் அல்லது தொடுதல் தேவை. வரைபடத்தில் உள்ள ஒவ்வொன்றும் அதே பக்கத்தில் எழுத்தாகவும் பட்டியலிடப்பட்டுள்ளது.',
    'ஏதேனும் உங்களுக்குச் சரியாக வேலை செய்யவில்லை எனில், வார்டு அலுவலகத்திடம் தெரிவிக்கவும்.',
  ],
  help_title: 'உதவி',
  help_items: [
    ['புகார் அளிப்பது எப்படி?', '"புகார் அளிக்க" என்பதைத் திறந்து, எது பழுதடைந்துள்ளது என்பதைத் தேர்வு செய்து, விவரித்து, வரைபடத்தில் இடத்தைத் தொட்டுச் சமர்ப்பிக்கவும். புகைப்படம் உதவும், ஆனால் கட்டாயமில்லை.'],
    ['அடுத்து என்ன நடக்கும்?', 'அந்த இடம் குறித்து முன்பு வந்த எல்லாப் புகார்களுடனும் உங்கள் புகார் இணைக்கப்படும். பொறியாளர் பரிசீலித்துப் பழுது நீக்கப் பணியை ஒதுக்குவார்.'],
    ['எப்படிக் கண்காணிப்பது?', '"எனது புகார்கள்" என்பதைத் திறக்கவும். ஒவ்வொரு புகாரும் அதன் நிலைகளையும் இலக்குத் தேதியையும் காட்டும்.'],
    ['"ஏற்கனவே பதிவில் உள்ளது" என்றால் என்ன?', 'இதே இடத்தை முன்பே யாரோ புகாரளித்துள்ளனர். உங்கள் புகார் அந்த வரலாற்றில் சேர்க்கப்படும்; அது மீண்டும் மீண்டும் பழுதடைவதை மாநகராட்சி அறிய உதவும்.'],
    ['யாரைத் தொடர்புகொள்வது?', 'இது ஒரு முன்மாதிரி. உண்மையான சேவையில், வார்டு அலுவலகத் தொடர்பு விவரங்கள் இங்கே காட்டப்படும்.'],
  ],
}

const DICTS = { en: EN, ta: TA }
const MONTHS = {
  en: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
  ta: ['ஜனவரி', 'பிப்ரவரி', 'மார்ச்', 'ஏப்ரல்', 'மே', 'ஜூன்', 'ஜூலை', 'ஆகஸ்ட்', 'செப்டம்பர்', 'அக்டோபர்', 'நவம்பர்', 'டிசம்பர்'],
}
const DOW = { en: ['M', 'T', 'W', 'T', 'F', 'S', 'S'], ta: ['தி', 'செ', 'பு', 'வி', 'வெ', 'ச', 'ஞா'] }

const Ctx = createContext(null)

export function PrefsProvider({ children }) {
  const [lang, setLangState] = useState(() => (load('cm.lang', 'en') === 'ta' ? 'ta' : 'en'))
  const [size, setSizeState] = useState(() => (SIZES[load('cm.size', 'normal')] ? load('cm.size', 'normal') : 'normal'))
  useEffect(() => { document.documentElement.lang = lang === 'ta' ? 'ta' : 'en' }, [lang])
  useEffect(() => { document.documentElement.style.fontSize = `${SIZES[size]}px` }, [size])
  const setLang = (l) => { setLangState(l); save('cm.lang', l) }
  const setSize = (s) => { setSizeState(s); save('cm.size', s) }
  const t = (key, vars = {}) => {
    let s = DICTS[lang][key] ?? EN[key] ?? key
    for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v)
    return s
  }
  const date = (iso) => (iso ? new Date(iso).toLocaleDateString(lang === 'ta' ? 'ta-IN' : 'en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—')
  return <Ctx.Provider value={{ lang, setLang, size, setSize, t, date, months: MONTHS[lang], dow: DOW[lang] }}>{children}</Ctx.Provider>
}

export const usePrefs = () => useContext(Ctx)

/** Staff dashboards are English only: same text-size control, no language switch. */
export function EnglishOnly({ children }) {
  const p = usePrefs()
  useEffect(() => {
    document.documentElement.lang = 'en'
    return () => { document.documentElement.lang = p.lang === 'ta' ? 'ta' : 'en' }
  }, [p.lang])
  const t = (key, vars = {}) => {
    let s = EN[key] ?? key
    for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v)
    return s
  }
  const date = (iso) => (iso ? new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—')
  return <Ctx.Provider value={{ ...p, lang: 'en', setLang: null, t, date, months: MONTHS.en, dow: DOW.en }}>{children}</Ctx.Provider>
}

/** Translate one citizen progress step from its key. */
export function stepLabel(t, s) {
  if (s.key === 'assigned' && s.contractor) return t('step_assigned_to', { c: s.contractor })
  if (s.key === 'fixed' && s.kind) return t(s.kind === 'permanent' ? 'step_fixed_permanent' : 'step_fixed_temporary')
  return s.key ? t(`step_${s.key}`) : s.label
}
