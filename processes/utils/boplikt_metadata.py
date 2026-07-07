"""Felles output-schema for bopliktsjekk-prosessorer."""

from processes.utils.boplikt_db import Column

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
                Column.GJELDER_FOR_BRUKT_SOM_HELARSBOLIG.value: {
                    "type": "boolean",
                    "description": "Angir om nedsatt konsesjonsgrense med boplikt gjelder for bebygd eiendom som er eller har vært brukt som helårsbolig.",
                },
                Column.GJELDER_FOR_BOLIG_IKKE_TATT_I_BRUK.value: {
                    "type": "boolean",
                    "description": "Angir om nedsatt konsesjonsgrense med boplikt gjelder for bolig under oppføring eller bolig som ikke er tatt i bruk som helårsbolig.",
                },
                Column.GJELDER_FOR_UBEBYGD_BOLIGTOMT.value: {
                    "type": "boolean",
                    "description": "Angir om nedsatt konsesjonsgrense med boplikt gjelder for ubebygd tomt regulert til boligformål.",
                },
                Column.HAR_UNNTAK_FRA_SLEKTSKAPSUNNTAK.value: {
                    "type": "boolean",
                    "description": "Angir om kommunen har innført unntak fra slektskapsunntaket.",
                },
                Column.ANDRE_LOKALE_AVGRENSNINGER.value: {
                    "type": "string",
                    "nullable": True,
                    "description": "Andre lokale begrensninger eller vilkår som ikke dekkes av de andre feltene.",
                },
                Column.HAR_USIKKER_AVGRENSNING.value: {
                    "type": "boolean",
                    "description": "Angir om bopliktsområdets geometriske avgrensning er usikker og må vurderes manuelt i tråd med forskriften. Verdi = True: Avgrensningen er usikker. Verdi = False: Avgrensningen er ikke usikker.",
                },
            },
        },
    }
}
