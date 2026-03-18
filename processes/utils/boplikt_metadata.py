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
                "bebygdEiendom": {
                    "type": "boolean",
                    "description": "Nedsatt konsesjonsgrense for bopliktområdet gjelder for bebygd eiendom som er eller har vært i bruk som helårsbolig.",
                },
                "ikkeHelarsboligUnderOppforing": {
                    "type": "boolean",
                    "description": "Nedsatt konsesjonsgrense for bopliktområdet gjelder for eiendom med bebyggelse som ikke er tatt i bruk som helårsbolig, herunder eiendom under oppføring regulert til boligformål.",
                },
                "ubebygdTomt": {
                    "type": "boolean",
                    "description": "Nedsatt konsesjonsgrense for bopliktområdet gjelder for ubebygd tomt regulert til boligformål.",
                },
                "unntakFraSlektskapsunntak": {
                    "type": "boolean",
                    "description": "Angir om det er innført unntak fra slektskapsunntaket.",
                },
                "andreAvgrensninger": {
                    "type": "string",
                    "nullable": True,
                    "description": "Andre materielle avgrensninger gitt i lokal bopliktforskrift.",
                },
                "usikkerAvgrensning": {
                    "type": "boolean",
                    "description": "Angir hvorvidt bopliktområdets geometriske representasjon er entydig definert. Dersom usikker (true) må det manuelt vurderes i tråd med forskriftens materielle vilkår.",
                },
            },
        },
    }
}
