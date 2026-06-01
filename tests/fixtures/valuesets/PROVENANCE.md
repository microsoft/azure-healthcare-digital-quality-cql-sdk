# Value set fixtures

Minimal expansions of the value sets referenced by the three MVP measures
(CMS165v9, CMS122v11, ePC-02). Each file is a FHIR R4 ValueSet resource with
a hand-curated `expansion.contains` list covering the codes used by the
patient bundle fixtures in `../bundles/`.

These are NOT full VSAC expansions — they only need to be rich enough to
make the fixture tests deterministic. For production use, the
`StaticTerminologyProvider` accepts any directory of full ValueSet
resources; replace these with VSAC snapshots when needed.

| Value set                              | OID-style URL                                                            | Includes                       |
|----------------------------------------|--------------------------------------------------------------------------|---------------------------------|
| Essential Hypertension                 | 2.16.840.1.113883.3.464.1003.104.12.1011                                 | ICD-10 I10                      |
| Outpatient Encounter                   | 2.16.840.1.113883.3.464.1003.101.12.1061                                 | CPT 99213, 99214                |
| End Stage Renal Disease                | 2.16.840.1.113883.3.464.1003.109.12.1029                                 | ICD-10 N18.6                    |
| Dialysis Services                      | 2.16.840.1.113883.3.464.1003.109.12.1013                                 | CPT 90935                       |
| Kidney Transplant                      | 2.16.840.1.113883.3.464.1003.109.12.1012                                 | CPT 50360                       |
| Pregnancy                              | 2.16.840.1.113883.3.464.1003.111.12.1012                                 | ICD-10 Z34.00                   |
| Hospice Care                           | 2.16.840.1.113883.3.464.1003.1048.12.1001                                | SNOMED 305336008                |
| Frailty                                | 2.16.840.1.113883.3.464.1003.1170.12.1001                                | ICD-10 R54                      |
| Advanced Illness                       | 2.16.840.1.113883.3.464.1003.1167.12.1001                                | ICD-10 C80.1                    |
| HbA1c Laboratory Test                  | 2.16.840.1.113883.3.464.1003.198.12.1013                                 | LOINC 4548-4                    |
| Diabetes                               | 2.16.840.1.113883.3.464.1003.103.12.1001                                 | ICD-10 E11.9                    |
| Single Live Birth                      | 2.16.840.1.113883.3.464.1003.111.12.1013                                 | ICD-10 O80                      |
| Eclampsia                              | 2.16.840.1.113883.3.464.1003.111.12.1099                                 | ICD-10 O15.9                    |
| ICU Admission                          | 2.16.840.1.113883.3.464.1003.111.12.1100                                 | SNOMED 309904001                |
| Blood Transfusion                      | 2.16.840.1.113883.3.464.1003.111.12.1101                                 | CPT 36430                       |
