library pa_dtr_library version '1.0.0'

using FHIR version '4.0.1'

include FHIRHelpers version '4.0.001' called FHIRHelpers

codesystem "SNOMEDCT": 'http://snomed.info/sct'

codesystem "RxNorm": 'http://www.nlm.nih.gov/research/umls/rxnorm'

code "Neurologic deficit (finding)": '230145002' from "SNOMEDCT"

code "Low back pain (finding)": '279039007' from "SNOMEDCT"

code "Physical therapy procedure (procedure)": '710958004' from "SNOMEDCT"

code "NSAID (medication)": '849574' from "RxNorm"

context Patient

/* Returns active member ID from Coverage */
define MemberId:
  singleton from ([Coverage] C where C.status = 'active').identifier.value

                                   
/* Objective neurologic deficit (SNOMED 26544005) present */
define NeurologicDeficitPresent:
    if Exists([Observation: "Neurologic deficit (finding)"])
    then 'Yes' else 'No'

/* Objective Conservative Therapy initiated */
define ConservativeTherapyInitiated:
  if Exists([Procedure: "Physical therapy procedure (procedure)"])
    or Exists([MedicationRequest: "NSAID (medication)"]) 
  then 'Yes' else 'No'
define WeeksOfLowBackPain:
// Low back pain SNOMED 279039007
case
  when Exists([Condition: "Low back pain (finding)"])
    then
      difference in weeks between (First([Condition: "Low back pain (finding)"]).onset as FHIR.dateTime)
        and Now()
  else null
end