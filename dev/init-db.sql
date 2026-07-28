CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS kommuneinfo;

CREATE TABLE kommuneinfo.bopliktomraade (
    kommunenummer        text PRIMARY KEY,
    delvis_boplikt       boolean NOT NULL,
    bebygd_eiendom       text,
    helaarsbolig         text,
    ubebygd_tomt         text,
    slektskapsunntak     text,
    andre_avgrensninger  text,
    usikker_avgrensning  boolean,
    omrade               geometry(MultiPolygon, 25833) NOT NULL
);

CREATE INDEX bopliktomraade_omrade_gix
    ON kommuneinfo.bopliktomraade USING gist (omrade);

-- 1) Område som dekker eksempel-geometrien i bopliktsjekk_geometri.py
INSERT INTO kommuneinfo.bopliktomraade VALUES (
    '4601', true,
    'Gjelder', 'Gjelder', 'Gjelder ikke', 'Gjelder',
    NULL, false,
    ST_Multi(ST_GeomFromText(
        'POLYGON((68900 6627300, 69100 6627300, 69100 6627400, 68900 6627400, 68900 6627300))',
        25833))
);

-- 2) Full boplikt for hele kommunen
INSERT INTO kommuneinfo.bopliktomraade VALUES (
    '0301', false,
    'Gjelder', 'Gjelder', 'Gjelder', 'Gjelder ikke',
    NULL, false,
    ST_Multi(ST_GeomFromText(
        'POLYGON((260000 6650000, 261000 6650000, 261000 6651000, 260000 6651000, 260000 6650000))',
        25833))
);

-- 3) Område med usikker avgrensning
INSERT INTO kommuneinfo.bopliktomraade VALUES (
    '1806', true,
    'Gjelder ikke', 'Gjelder', 'Gjelder', 'Gjelder',
    'Avgrensning under revisjon.', true,
    ST_Multi(ST_GeomFromText(
        'POLYGON((599500 7596500, 600500 7596500, 600500 7597500, 599500 7597500, 599500 7596500))',
        25833))
);
