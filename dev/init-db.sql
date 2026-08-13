CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS inndelinger;

CREATE TABLE inndelinger.bopliktomraade (
    "lokalId"                          text PRIMARY KEY,
    kommunenummer                    text NOT NULL,
    "gjelderKunDelAvKommunen"        boolean NOT NULL,
    "gjelderForBruktSomHelarsbolig"  boolean,
    "gjelderForBoligIkkeTattIBruk"   boolean,
    "gjelderForUbebygdBoligtomt"     boolean,
    "harUnntakFraSlektskapsunntak"   boolean,
    "andreLokaleAvgrensninger"       text,
    "harUsikkerAvgrensning"          boolean,
    omrade                           geometry(MultiPolygon, 25833) NOT NULL
);

CREATE INDEX bopliktomraade_omrade_gix
    ON inndelinger.bopliktomraade USING gist (omrade);

CREATE INDEX bopliktomraade_kommunenummer_idx
    ON inndelinger.bopliktomraade (kommunenummer);

INSERT INTO inndelinger.bopliktomraade (
    "lokalId",
    kommunenummer,
    "gjelderKunDelAvKommunen",
    "gjelderForBruktSomHelarsbolig",
    "gjelderForBoligIkkeTattIBruk",
    "gjelderForUbebygdBoligtomt",
    "harUnntakFraSlektskapsunntak",
    "andreLokaleAvgrensninger",
    "harUsikkerAvgrensning",
    omrade
) VALUES (
    '4601-001',
    '4601', true, true, true, false, true, NULL, false,
    ST_Multi(ST_GeomFromText(
        'POLYGON((68900 6627300, 69100 6627300, 69100 6627400, 68900 6627400, 68900 6627300))',
        25833))
);

INSERT INTO inndelinger.bopliktomraade (
    "lokalId",
    kommunenummer,
    "gjelderKunDelAvKommunen",
    "gjelderForBruktSomHelarsbolig",
    "gjelderForBoligIkkeTattIBruk",
    "gjelderForUbebygdBoligtomt",
    "harUnntakFraSlektskapsunntak",
    "andreLokaleAvgrensninger",
    "harUsikkerAvgrensning",
    omrade
) VALUES (
    '4601-002',
    '4601', true, true, true, false, true, NULL, false,
    ST_Multi(ST_GeomFromText(
        'POLYGON((69400 6627300, 69600 6627300, 69600 6627400, 69400 6627400, 69400 6627300))',
        25833))
);


-- Full boplikt for hele kommunen
INSERT INTO inndelinger.bopliktomraade (
    "lokalId",
    kommunenummer,
    "gjelderKunDelAvKommunen",
    "gjelderForBruktSomHelarsbolig",
    "gjelderForBoligIkkeTattIBruk",
    "gjelderForUbebygdBoligtomt",
    "harUnntakFraSlektskapsunntak",
    "andreLokaleAvgrensninger",
    "harUsikkerAvgrensning",
    omrade
) VALUES (
    '0301-001',
    '0301', false, true, true, true, false, NULL, false,
    ST_Multi(ST_GeomFromText(
        'POLYGON((260000 6650000, 261000 6650000, 261000 6651000, 260000 6651000, 260000 6650000))',
        25833))
);

-- Område med usikker avgrensning
INSERT INTO inndelinger.bopliktomraade (
    "lokalId",
    kommunenummer,
    "gjelderKunDelAvKommunen",
    "gjelderForBruktSomHelarsbolig",
    "gjelderForBoligIkkeTattIBruk",
    "gjelderForUbebygdBoligtomt",
    "harUnntakFraSlektskapsunntak",
    "andreLokaleAvgrensninger",
    "harUsikkerAvgrensning",
    omrade
) VALUES (
    '1806-001',
    '1806', true, true, false, true, true, 'Avgrensning under revisjon.', true,
    ST_Multi(ST_GeomFromText(
        'POLYGON((599500 7596500, 600500 7596500, 600500 7597500, 599500 7597500, 599500 7596500))',
        25833))
);

-- Naboområde som deler grense med 4601 i x=69100.
INSERT INTO inndelinger.bopliktomraade (
    "lokalId",
    kommunenummer,
    "gjelderKunDelAvKommunen",
    "gjelderForBruktSomHelarsbolig",
    "gjelderForBoligIkkeTattIBruk",
    "gjelderForUbebygdBoligtomt",
    "harUnntakFraSlektskapsunntak",
    "andreLokaleAvgrensninger",
    "harUsikkerAvgrensning",
    omrade
) VALUES (
    '4602-001',
    '4602', true, true, false, false, false, NULL, false,
    ST_Multi(ST_GeomFromText(
        'POLYGON((69100 6627300, 69300 6627300, 69300 6627400, 69100 6627400, 69100 6627300))',
        25833))
);