"""English / Telugu text for everything the analysis engine says.

The engine emits message CODES + params; this module turns them into {"en": ..., "te": ...}.
Having one source for analysis text keeps the JSON API, the web UI and the PDF consistent.
Telugu strings should be reviewed by a native speaker / hydrogeologist before production use.
"""
from __future__ import annotations

import re
from typing import Any

LANGS = ("en", "te")


def _m(en: str, te: str) -> dict:
    return {"en": en, "te": te}


MESSAGES: dict[str, dict] = {
    # ------------------------------------------------------------------ warnings
    "demo_data": _m(
        "DEMONSTRATION DATA: this result is computed from synthetic sample data. It says nothing about real "
        "groundwater and must not be used for any drilling decision.",
        "ప్రదర్శన డేటా: ఈ ఫలితం కృత్రిమ నమూనా డేటాతో లెక్కించబడింది. ఇది నిజమైన భూగర్భ జలాల గురించి ఏమీ "
        "చెప్పదు; బోరు వేసే నిర్ణయానికి దీనిని ఉపయోగించకూడదు."),
    "hard_rock_variability": _m(
        "In hard-rock terrain (granite, gneiss and similar) water sits in fractures, so borewell yield can change "
        "sharply within tens of metres. A regional index cannot capture this; on-site investigation matters most here.",
        "గట్టి శిలల (గ్రానైట్, నైస్ వంటివి) ప్రాంతాల్లో నీరు పగుళ్లలో ఉంటుంది కాబట్టి, కొన్ని పదుల మీటర్ల "
        "దూరంలోనే బోరు దిగుబడి గణనీయంగా మారవచ్చు. ప్రాంతీయ సూచిక దీనిని పట్టుకోలేదు; ఇక్కడ క్షేత్ర స్థాయి "
        "పరిశీలన అత్యంత ముఖ్యం."),
    "local_better_than_regional": _m(
        "Nearby borewell/survey records ({n} within {radius_km} km) are noticeably better than the regional index "
        "suggests. The final score was raised, but results can still differ from plot to plot.",
        "సమీపంలోని బోరుబావి/సర్వే రికార్డులు ({radius_km} కి.మీ. లోపు {n}) ప్రాంతీయ సూచిక సూచించిన దానికంటే "
        "గణనీయంగా మెరుగ్గా ఉన్నాయి. తుది స్కోరు పెంచబడింది; అయినా స్థలం నుంచి స్థలానికి ఫలితాలు మారవచ్చు."),
    "local_worse_than_regional": _m(
        "Nearby borewell/survey records ({n} within {radius_km} km) are noticeably worse than the regional index "
        "suggests (for example dry or low-yield wells). The final score was lowered.",
        "సమీపంలోని బోరుబావి/సర్వే రికార్డులు ({radius_km} కి.మీ. లోపు {n}) ప్రాంతీయ సూచిక సూచించిన దానికంటే "
        "గణనీయంగా అధ్వాన్నంగా ఉన్నాయి (ఉదా: నీరు లేని లేదా తక్కువ దిగుబడి బోర్లు). తుది స్కోరు తగ్గించబడింది."),
    "ml_disagrees": _m(
        "The optional statistical model disagrees with the index (it estimates a {p}% chance of a productive "
        "borewell). Treat the result with extra caution.",
        "ఐచ్ఛిక గణాంక నమూనా సూచికతో ఏకీభవించడం లేదు (ఉత్పాదక బోరు ఉండే అవకాశం {p}% అని అంచనా). ఫలితాన్ని "
        "అదనపు జాగ్రత్తతో పరిగణించండి."),
    "declining_water_levels": _m(
        "Nearby monitoring wells ({n}) show the pre-monsoon water table deepening by about {rate_m} m per year. "
        "Heavy extraction or weak recharge can reduce long-term borewell reliability.",
        "సమీప పర్యవేక్షణ బావులు ({n}) వర్షాకాలానికి ముందు భూగర్భ నీటి మట్టం ఏడాదికి సుమారు {rate_m} మీ. "
        "లోతుకు పడిపోతున్నట్లు చూపుతున్నాయి. అధిక వినియోగం లేదా తక్కువ రీఛార్జ్ వల్ల దీర్ఘకాలంలో బోరు "
        "విశ్వసనీయత తగ్గవచ్చు."),
    "low_location_accuracy": _m(
        "Your location accuracy is only about ±{accuracy_m} m. Borewell siting needs a precise position - mark the "
        "exact spot on the map and verify it in the field.",
        "మీ స్థాన ఖచ్చితత్వం సుమారు ±{accuracy_m} మీ. మాత్రమే. బోరు స్థానానికి ఖచ్చితమైన స్థానం అవసరం - "
        "మ్యాప్‌లో సరైన స్థలాన్ని గుర్తించి, క్షేత్రంలో నిర్ధారించుకోండి."),
    "gw_over_exploited": _m(
        "This area is categorised as 'over-exploited' in the groundwater resource assessment. Extra permissions or "
        "restrictions on new borewells may apply.",
        "భూగర్భ జల వనరుల అంచనాలో ఈ ప్రాంతం 'అతిగా వినియోగించబడిన' వర్గంలో ఉంది. కొత్త బోర్లకు అదనపు అనుమతులు "
        "లేదా ఆంక్షలు వర్తించవచ్చు."),
    "gw_critical": _m(
        "This area is categorised as 'critical' in the groundwater resource assessment. Extra permissions or "
        "restrictions on new borewells may apply.",
        "భూగర్భ జల వనరుల అంచనాలో ఈ ప్రాంతం 'సంక్షోభ (క్రిటికల్)' వర్గంలో ఉంది. కొత్త బోర్లకు అదనపు అనుమతులు "
        "లేదా ఆంక్షలు వర్తించవచ్చు."),
    "gw_saline": _m(
        "Groundwater in this area is flagged as saline in the resource assessment. Even where water is found it may "
        "not be fit for use - get the water quality tested.",
        "వనరుల అంచనాలో ఈ ప్రాంతంలోని భూగర్భ జలం ఉప్పగా (లవణీయంగా) ఉన్నట్లు గుర్తించబడింది. నీరు దొరికినా "
        "వినియోగానికి అనువుగా ఉండకపోవచ్చు - నీటి నాణ్యత పరీక్ష చేయించండి."),
    "confidence_capped": _m(
        "Confidence was limited to 'medium' because there are too few nearby borewell/survey records to support a "
        "higher level.",
        "సమీపంలో తగినన్ని బోరుబావి/సర్వే రికార్డులు లేనందున నమ్మకం స్థాయి 'మధ్యస్థం'కు పరిమితం చేయబడింది."),

    # ------------------------------------------------------------------ data gaps
    "gap_out_of_coverage": _m(
        "This location is outside the area for which groundwater datasets are currently loaded, so no potential "
        "class is given.",
        "ఈ స్థానం ప్రస్తుతం భూగర్భ జల డేటా అందుబాటులో ఉన్న ప్రాంతం వెలుపల ఉంది, కాబట్టి సామర్థ్య వర్గం "
        "ఇవ్వబడలేదు."),
    "gap_factor": _m(
        "No data available for: {factor}. It was left out of the calculation (not estimated).",
        "{factor} కోసం డేటా అందుబాటులో లేదు. దానిని లెక్కింపు నుంచి మినహాయించాం (అంచనా వేయలేదు)."),
    "gap_water_level": _m(
        "Water-table depth is unavailable for this location.",
        "ఈ స్థానానికి భూగర్భ నీటి మట్టం లోతు అందుబాటులో లేదు."),
    "gap_water_level.no_wells_in_radius": _m(
        "No groundwater monitoring wells within {radius_km} km, so the water-table depth is unavailable.",
        "{radius_km} కి.మీ. పరిధిలో భూగర్భ జల పర్యవేక్షణ బావులు లేవు, కాబట్టి నీటి మట్టం లోతు అందుబాటులో లేదు."),
    "gap_water_level.too_few_wells": _m(
        "Fewer than 2 monitoring wells with recent pre-monsoon readings within {radius_km} km; the water-table "
        "depth is not estimated.",
        "{radius_km} కి.మీ. పరిధిలో ఇటీవలి వర్షాకాలానికి-ముందు రీడింగ్‌లు ఉన్న పర్యవేక్షణ బావులు 2 కంటే "
        "తక్కువ; నీటి మట్టం లోతును అంచనా వేయలేదు."),
    "gap_water_level.no_recent_readings": _m(
        "Monitoring wells exist nearby but have no recent readings; the water-table depth is unavailable.",
        "సమీపంలో పర్యవేక్షణ బావులు ఉన్నా వాటికి ఇటీవలి రీడింగ్‌లు లేవు; నీటి మట్టం లోతు అందుబాటులో లేదు."),
    "gap_no_borewell_records": _m(
        "No historical borewell records within {radius_km} km.",
        "{radius_km} కి.మీ. పరిధిలో గత బోరుబావి రికార్డులు లేవు."),
    "gap_few_borewell_records": _m(
        "Only {n} historical borewell record(s) nearby - too few to adjust the regional result.",
        "సమీపంలో కేవలం {n} గత బోరుబావి రికార్డు(లు) మాత్రమే ఉన్నాయి - ప్రాంతీయ ఫలితాన్ని సర్దుబాటు చేయడానికి "
        "చాలవు."),
    "gap_no_geophysics": _m(
        "No geophysical (VES/ERT) survey within {radius_km} km.",
        "{radius_km} కి.మీ. పరిధిలో జియోఫిజికల్ (VES/ERT) సర్వే లేదు."),
    "gap_depth_range": _m(
        "A drilling-depth range cannot be given for this location.",
        "ఈ స్థానానికి బోరు లోతు పరిధిని ఇవ్వలేము."),
    "gap_depth_range.no_records": _m(
        "No nearby borewell records, so no drilling-depth range can be given.",
        "సమీపంలో బోరుబావి రికార్డులు లేవు, కాబట్టి బోరు లోతు పరిధిని ఇవ్వలేము."),
    "gap_depth_range.insufficient_records": _m(
        "Only {n} productive borewell record(s) within {radius_km} km; at least {n_required} are needed before a "
        "drilling-depth range is shown.",
        "{radius_km} కి.మీ. పరిధిలో ఉత్పాదక బోరుబావి రికార్డులు {n} మాత్రమే ఉన్నాయి; బోరు లోతు పరిధి చూపడానికి "
        "కనీసం {n_required} అవసరం."),
    "gap_gw_category": _m(
        "The groundwater resource category (safe / critical / over-exploited) for this area is not available in the "
        "loaded data.",
        "ఈ ప్రాంతానికి భూగర్భ జల వనరుల వర్గం (సురక్షిత / సంక్షోభ / అతిగా వినియోగించబడిన) లోడ్ చేసిన డేటాలో "
        "అందుబాటులో లేదు."),

    # ------------------------------------------------------------------ recommendations
    "consult_hydrogeologist": _m(
        "Consult a qualified hydrogeologist or your State Ground Water Department before drilling. This tool "
        "supports, but never replaces, an on-site assessment.",
        "బోరు వేసే ముందు అర్హత కలిగిన హైడ్రోజియాలజిస్టును లేదా రాష్ట్ర భూగర్భ జల శాఖను సంప్రదించండి. ఈ సాధనం "
        "క్షేత్ర స్థాయి పరిశీలనకు సహాయపడుతుంది, కానీ దానికి ప్రత్యామ్నాయం కాదు."),
    "geophysical_survey": _m(
        "Commission a geophysical survey (Vertical Electrical Sounding or Electrical Resistivity Tomography) at "
        "your exact plot to locate fractures and weathered zones before choosing a drilling point.",
        "బోరు స్థానం ఎంచుకునే ముందు, పగుళ్లు మరియు శైథిల్య మండలాలను గుర్తించడానికి మీ స్థలంలోనే జియోఫిజికల్ "
        "సర్వే (వర్టికల్ ఎలక్ట్రికల్ సౌండింగ్ లేదా ఎలక్ట్రికల్ రెసిస్టివిటీ టోమోగ్రఫీ) చేయించండి."),
    "verify_with_geophysics_on_site": _m(
        "A geophysical survey exists nearby, but it may not represent your plot. Have the drilling point verified "
        "on site by a hydrogeologist.",
        "సమీపంలో జియోఫిజికల్ సర్వే ఉంది, కానీ అది మీ స్థలాన్ని ప్రతిబింబించకపోవచ్చు. హైడ్రోజియాలజిస్టుతో బోరు "
        "స్థానాన్ని క్షేత్రంలో ధృవీకరించుకోండి."),
    "alternatives_low_potential": _m(
        "Groundwater potential looks limited here. Consider alternatives or supplements: rainwater harvesting, farm "
        "ponds, recharge structures, a shared water source, or water-saving irrigation.",
        "ఇక్కడ భూగర్భ జల సామర్థ్యం పరిమితంగా కనిపిస్తోంది. ప్రత్యామ్నాయాలు పరిశీలించండి: వర్షపు నీటి సంరక్షణ, "
        "వ్యవసాయ కుంటలు, రీఛార్జ్ నిర్మాణాలు, ఉమ్మడి నీటి వనరు, నీటిని ఆదా చేసే సాగు పద్ధతులు."),
    "dont_drill_deeper_blindly": _m(
        "Do not assume that drilling deeper will find water: in hard-rock areas water-bearing fractures generally "
        "become fewer with depth, so deeper drilling often adds cost without adding yield.",
        "ఇంకా లోతుగా తవ్వితే నీరు దొరుకుతుందని భావించవద్దు: గట్టి శిలల ప్రాంతాల్లో లోతు పెరిగే కొద్దీ నీటినిచ్చే "
        "పగుళ్లు సాధారణంగా తగ్గుతాయి; అందువల్ల మరింత లోతుకు తవ్వడం తరచుగా ఖర్చు పెంచుతుంది, దిగుబడి పెంచదు."),
    "siting_matters": _m(
        "Exact siting within your plot matters. In fractured rock a spot a few tens of metres away can perform very "
        "differently - choose the point using a site survey.",
        "మీ స్థలంలో ఖచ్చితమైన బోరు స్థానం ముఖ్యం. పగుళ్ల శిలల్లో కొన్ని పదుల మీటర్ల దూరంలోని స్థానం పూర్తిగా "
        "భిన్నమైన ఫలితం ఇవ్వవచ్చు - సర్వే ఆధారంగా స్థానం ఎంచుకోండి."),
    "check_permissions": _m(
        "Check the permission, registration and rig-operator requirements that apply in your area with the State "
        "Ground Water Department and local authorities before drilling.",
        "బోరు వేసే ముందు మీ ప్రాంతంలో వర్తించే అనుమతి, నమోదు, రిగ్ నిర్వాహకుల నిబంధనల గురించి రాష్ట్ర భూగర్భ జల "
        "శాఖ మరియు స్థానిక అధికారులను అడిగి తెలుసుకోండి."),
    "seal_unused_borewells": _m(
        "Safety: always cap or fill any unused, dry or failed borewell. Open borewells are a serious hazard, "
        "especially for children.",
        "భద్రత: ఉపయోగంలో లేని, నీరు లేని లేదా విఫలమైన బోరుబావులను ఎల్లప్పుడూ మూసివేయండి లేదా పూడ్చండి. తెరిచి "
        "ఉన్న బోరుబావులు ముఖ్యంగా పిల్లలకు తీవ్ర ప్రమాదం."),
    "field_study_required": _m(
        "There is not enough data here for a reliable estimate. A field investigation by a hydrogeologist "
        "(including a geophysical survey) is essential.",
        "ఇక్కడ నమ్మదగిన అంచనాకు తగినంత డేటా లేదు. హైడ్రోజియాలజిస్టు చేసే క్షేత్ర పరిశీలన (జియోఫిజికల్ "
        "సర్వేతో సహా) తప్పనిసరి."),

    # ------------------------------------------------------------------ notes / status
    "disclaimer": _m(
        "This report shows groundwater POTENTIAL estimated from public datasets and a documented method. It is not "
        "a confirmation that water exists at this spot, not a guarantee of borewell success, yield, depth or water "
        "quality, and not a substitute for an on-site investigation by a qualified professional.",
        "ఈ నివేదిక ప్రజా డేటా సెట్లు మరియు నమోదు చేసిన పద్ధతి ఆధారంగా అంచనా వేసిన భూగర్భ జల సామర్థ్యాన్ని "
        "(POTENTIAL) మాత్రమే చూపుతుంది. ఈ స్థలంలో నీరు ఉందని ధృవీకరణ కాదు; బోరు విజయం, దిగుబడి, లోతు లేదా "
        "నీటి నాణ్యతకు హామీ కాదు; అర్హత కలిగిన నిపుణుడి క్షేత్ర పరిశీలనకు ప్రత్యామ్నాయం కాదు."),
    "potential_note": _m(
        "Groundwater potential is NOT confirmed underground water. It indicates how favourable ground conditions "
        "are for storing and yielding water.",
        "భూగర్భ జల సామర్థ్యం అంటే నిర్ధారిత భూగర్భ నీరు కాదు. నీటిని నిల్వ చేయడానికి, ఇవ్వడానికి భూమి "
        "పరిస్థితులు ఎంత అనుకూలంగా ఉన్నాయో ఇది సూచిస్తుంది."),
    "confidence_note": _m(
        "Confidence describes how much real data supports this result. It is not the probability that a borewell "
        "will find water.",
        "నమ్మకం స్థాయి అంటే ఈ ఫలితానికి ఎంత నిజమైన డేటా మద్దతు ఉందో తెలుపుతుంది. బోరులో నీరు పడే సంభావ్యత "
        "కాదు."),
    "depth_note": _m(
        "Depths shown are what was actually drilled in nearby productive borewells (10th-90th percentile). They "
        "are not a prediction for your plot.",
        "చూపిన లోతులు సమీపంలోని ఉత్పాదక బోర్లలో వాస్తవంగా తవ్విన లోతులు (10వ–90వ శతాంశం). ఇది మీ స్థలానికి "
        "అంచనా కాదు."),
    "water_table_note": _m(
        "The depth to the water table in nearby monitoring wells is not the depth to which a borewell must be "
        "drilled.",
        "సమీప పర్యవేక్షణ బావులలోని భూగర్భ నీటి మట్టం లోతు, బోరు ఎంత లోతు వేయాలనే దానికి సమానం కాదు."),
    "insufficient.low_coverage": _m(
        "Too few datasets cover this location to classify it reliably.",
        "ఈ స్థానాన్ని నమ్మదగినట్లు వర్గీకరించడానికి తగినన్ని డేటా సెట్లు లేవు."),
    "insufficient.missing_required": _m(
        "The geological formation (lithology) at this location is unknown, so it cannot be classified.",
        "ఈ స్థానంలోని భౌగోళిక శిలా నిర్మాణం (లిథాలజీ) తెలియదు, కాబట్టి వర్గీకరించలేము."),
    "ml.not_available": _m(
        "Statistical model: not available (it needs enough real borewell records and a passing validation score).",
        "గణాంక నమూనా: అందుబాటులో లేదు (దీనికి తగినన్ని నిజమైన బోరుబావి రికార్డులు మరియు ధ్రువీకరణ స్కోరు "
        "అవసరం)."),
    "ml.available": _m(
        "Second opinion from a statistical model: estimated chance of a productive borewell {p}% (validated AUC "
        "{auc}; trained on {n} records).",
        "గణాంక నమూనా రెండవ అభిప్రాయం: ఉత్పాదక బోరు ఉండే అంచనా అవకాశం {p}% (ధ్రువీకరణ AUC {auc}; {n} "
        "రికార్డులపై శిక్షణ)."),
    "ml.demo_trained": _m(
        "This model was trained on synthetic demonstration data.",
        "ఈ నమూనా కృత్రిమ ప్రదర్శన డేటాపై శిక్షణ పొందింది."),
}

# Short labels shared by the API payload and the PDF.
LABELS: dict[str, dict] = {
    "app_name": _m("Borewell Water Finder", "భూగర్భ జలాల అన్వేషణ"),
    "report_title": _m("Groundwater Potential Report", "భూగర్భ జల సామర్థ్య నివేదిక"),
    "generated_on": _m("Generated on", "తయారు చేసిన తేదీ"),
    "location": _m("Location", "స్థానం"),
    "coordinates": _m("Coordinates", "అక్షాంశ-రేఖాంశాలు"),
    "state": _m("State", "రాష్ట్రం"), "district": _m("District", "జిల్లా"),
    "mandal": _m("Mandal", "మండలం"), "village": _m("Village", "గ్రామం"),
    "nearest_place_note": _m(
        "Place names are the nearest known place (approximate), not an official boundary lookup.",
        "ప్రదేశ పేర్లు సమీప తెలిసిన ప్రదేశం ఆధారంగా (సుమారు) ఇవ్వబడ్డాయి; అధికారిక సరిహద్దు ఆధారిత గుర్తింపు కాదు."),
    "potential": _m("Groundwater potential", "భూగర్భ జల సామర్థ్యం"),
    "score": _m("Potential index (0-100)", "సామర్థ్య సూచిక (0-100)"),
    "regional_class": _m("Regional class (shown on the map)", "ప్రాంతీయ వర్గం (మ్యాప్‌లో చూపేది)"),
    "final_class": _m("Final class (after local evidence)", "తుది వర్గం (స్థానిక ఆధారాల తర్వాత)"),
    "confidence": _m("Confidence level", "నమ్మకం స్థాయి"),
    "conf_low": _m("Low", "తక్కువ"), "conf_medium": _m("Medium", "మధ్యస్థం"), "conf_high": _m("High", "అధికం"),
    "conf_component.coverage": _m("Share of factors with data", "డేటా ఉన్న అంశాల వాటా"),
    "conf_component.local_support": _m("Nearby borewell / survey records", "సమీప బోరుబావి / సర్వే రికార్డులు"),
    "conf_component.water_level_support": _m("Nearby monitoring wells", "సమీప పర్యవేక్షణ బావులు"),
    "conf_component.geophysics": _m("Geophysical survey nearby", "సమీపంలో జియోఫిజికల్ సర్వే"),
    "conf_component.recency": _m("Recency of water-level data", "నీటి మట్టం డేటా తాజాదనం"),
    "conf_component.consistency": _m("Agreement of local and regional evidence", "స్థానిక మరియు ప్రాంతీయ ఆధారాల సారూప్యత"),
    "factors": _m("How the index was calculated", "సూచిక ఎలా లెక్కించబడింది"),
    "factor": _m("Factor", "అంశం"), "value": _m("Value", "విలువ"), "factor_score": _m("Score", "స్కోరు"),
    "weight": _m("Weight", "బరువు"),
    "not_available": _m("Not available", "అందుబాటులో లేదు"),
    "not_applicable": _m("Not applicable", "వర్తించదు"),
    "water_table": _m("Water table (monitoring wells)", "భూగర్భ నీటి మట్టం (పర్యవేక్షణ బావులు)"),
    "pre_monsoon": _m("Pre-monsoon depth to water", "వర్షాకాలానికి ముందు నీటి మట్టం లోతు"),
    "post_monsoon": _m("Post-monsoon depth to water", "వర్షాకాలం తర్వాత నీటి మట్టం లోతు"),
    "wells_used": _m("Monitoring wells used", "ఉపయోగించిన పర్యవేక్షణ బావులు"),
    "depth_range": _m("Drilling depth seen in nearby productive borewells", "సమీప ఉత్పాదక బోర్లలో తవ్విన లోతు"),
    "local_evidence": _m("Local evidence", "స్థానిక ఆధారాలు"),
    "borewell_records_within": _m("Historical borewell records within {r} km",
                                  "{r} కి.మీ. పరిధిలో గతంలో వేసిన బోరుబావి రికార్డులు"),
    "nearest": _m("nearest", "అత్యంత సమీపం"),
    "depth_basis": _m("Based on {n} productive borewell record(s) within {r} km",
                      "{r} కి.మీ. పరిధిలో నీరు లభించిన {n} బోరుబావి రికార్డుల ఆధారంగా"),
    "trend_falling": _m("Water level is falling by about {m} m ({ft} ft) a year.",
                        "నీటి మట్టం ఏటా సుమారు {m} మీ. ({ft} అడుగులు) తగ్గుతోంది."),
    "trend_rising": _m("Water level is rising by about {m} m ({ft} ft) a year.",
                       "నీటి మట్టం ఏటా సుమారు {m} మీ. ({ft} అడుగులు) పెరుగుతోంది."),
    "trend_stable": _m("Water level has been roughly steady.", "నీటి మట్టం దాదాపు స్థిరంగా ఉంది."),
    "rainfall_recent": _m("Recent mean rainfall / long-term normal", "ఇటీవలి సగటు వర్షపాతం / దీర్ఘకాల సాధారణ వర్షపాతం"),
    "borewell_records": _m("Historical borewell records nearby", "సమీపంలోని గత బోరుబావి రికార్డులు"),
    "outcome.dry": _m("Dry", "నీరు లేదు"), "outcome.low": _m("Low yield", "తక్కువ దిగుబడి"),
    "outcome.moderate": _m("Moderate yield", "మధ్యస్థ దిగుబడి"), "outcome.good": _m("Good yield", "మంచి దిగుబడి"),
    "ves_surveys": _m("Geophysical surveys nearby", "సమీపంలోని జియోఫిజికల్ సర్వేలు"),
    "suitability.good": _m("Good", "మంచిది"), "suitability.moderate": _m("Moderate", "మధ్యస్థం"),
    "suitability.poor": _m("Poor", "బలహీనం"),
    "warnings": _m("Warnings", "హెచ్చరికలు"),
    "data_gaps": _m("Unavailable data", "అందుబాటులో లేని డేటా"),
    "recommendations": _m("Recommended next steps", "సిఫార్సు చేసిన తదుపరి చర్యలు"),
    "sources": _m("Data sources", "డేటా మూలాలు"), "source": _m("Source", "మూలం"),
    "publisher": _m("Publisher", "ప్రచురణకర్త"), "last_updated": _m("Last updated", "తాజా నవీకరణ"),
    "method": _m("Method", "పద్ధతి"),
    "disclaimer_title": _m("Important", "ముఖ్య గమనిక"),
    "demo_watermark": _m("DEMONSTRATION DATA", "ప్రదర్శన డేటా"),
    "status.out_of_coverage": _m("Outside the covered area", "అందుబాటులో ఉన్న ప్రాంతం వెలుపల"),
    "status.insufficient_data": _m("Insufficient data", "తగినంత సమాచారం లేదు"),
    "unit.ft": _m("ft", "అడుగులు"), "unit.m": _m("m", "మీ."), "unit.km": _m("km", "కి.మీ."),
    "unit.mm": _m("mm", "మి.మీ."), "unit.records": _m("records", "రికార్డులు"),
    "page": _m("Page", "పేజీ"),
}

GW_CATEGORY = {
    "safe": _m("Safe", "సురక్షితం"), "semi_critical": _m("Semi-critical", "పాక్షిక సంక్షోభం"),
    "critical": _m("Critical", "సంక్షోభం"), "over_exploited": _m("Over-exploited", "అతిగా వినియోగించబడింది"),
    "saline": _m("Saline", "లవణీయం"),
}

_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def placeholders(text: str) -> set[str]:
    return set(_PLACEHOLDER.findall(text))


def _fmt(v: Any, lang: str) -> str:
    if isinstance(v, dict):
        return _fmt(v.get(lang, v.get("en")), lang)
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else f"{v:g}"
    return "" if v is None else str(v)


def render(code: str, params: dict | None = None) -> dict:
    """{"en": text, "te": text} for a message code. Param values may be scalars or {"en","te"} dicts.
    A `reason` param selects the more specific `code.reason` text when one exists."""
    params = params or {}
    key = code
    reason = params.get("reason")
    if reason and f"{code}.{reason}" in MESSAGES:
        key = f"{code}.{reason}"
    entry = MESSAGES.get(key)
    if entry is None:
        return {"en": code, "te": code}
    out = {}
    for lang in LANGS:
        vals = {k: _fmt(v, lang) for k, v in params.items()}
        text = entry[lang]
        out[lang] = _PLACEHOLDER.sub(lambda m: vals.get(m.group(1), m.group(0)), text)
    return out


def label(key: str) -> dict:
    return LABELS[key]
