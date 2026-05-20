"""Felles output-schema for bopliktsjekk-prosessorer."""

BOPLIKTSJEKK_OUTPUT = {
    "resultat": {
        "title": "Bopliktsjekk-resultat",
        "schema": {
            "type": "object",
            "contentMediaType": "application/json",
            "properties": {
                "iBopliktomrade": {
                    "type": "string",
                    "description": "Om geometrien er i et bopliktområde. JA = helt innenfor, NEI = utenfor, DELVIS = delvis innenfor.",
                    "enum": ["JA", "NEI", "DELVIS"],
                },
                "gjelderForBruktSomHelarsbolig": {
                    "type": "boolean",
                    "description": "Angir om nedsatt konsesjonsgrense med boplikt gjelder for bebygd eiendom som er eller har vært brukt som helårsbolig.",
                },
                "gjelderForBoligIkkeTattIBruk": {
                    "type": "boolean",
                    "description": "Angir om nedsatt konsesjonsgrense med boplikt gjelder for bolig under oppføring eller bolig som ikke er tatt i bruk som helårsbolig.",
                },
                "gjelderForUbebygdBoligtomt": {
                    "type": "boolean",
                    "description": "Angir om nedsatt konsesjonsgrense med boplikt gjelder for ubebygd tomt regulert til boligformål.",
                },
                "harUnntakFraSlektskapsunntak": {
                    "type": "boolean",
                    "description": "Angir om kommunen har innført unntak fra slektskapsunntaket.",
                },
                "andreLokaleAvgrensninger": {
                    "type": "string",
                    "nullable": True,
                    "description": "Andre lokale begrensninger eller vilkår som ikke dekkes av de andre feltene.",
                },
                "harUsikkerAvgrensning": {
                    "type": "boolean",
                    "description": "Angir om bopliktsområdets geometriske avgrensning er usikker og må vurderes manuelt i tråd med forskriften. Verdi = True: Avgrensningen er usikker. Verdi = False: Avgrensningen er ikke usikker.",
                },
            },
        },
    }
}
