-- Adds the two India Post office records listed for PIN 500032.
-- Coordinates are an approximate PIN-area centre for demo map navigation only.
-- These records remain marked is_demo=true and must be replaced with verified office coordinates in production.
INSERT INTO pincodes (pincode, office_name, state_code, district_area_id, centroid, source_id, is_demo)
SELECT '500032', office_name, 'TG', 2,
       ST_SetSRID(ST_MakePoint(78.356000, 17.439900), 4326), 'demo_pincode', true
FROM (VALUES ('Gachibowli S.O'), ('MANUU S.O')) AS offices(office_name)
ON CONFLICT (pincode, office_name) DO UPDATE
SET centroid = EXCLUDED.centroid,
    district_area_id = EXCLUDED.district_area_id,
    source_id = EXCLUDED.source_id,
    is_demo = EXCLUDED.is_demo;
