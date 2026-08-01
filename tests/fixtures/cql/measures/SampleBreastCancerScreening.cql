library SampleBreastCancerScreening version '1.0.0'

// The standardized data model used by NCQA/CMS engines
using QICore version '4.1.1'

// Include global utility libraries for date parsing and calculation
include FHIRHelpers version '4.1.000' called FHIRHelpers

// Value sets managed by NLM VSAC for engine code-matching
valueset "Oid Breast Cancer Screening": 'http://nih.gov'
valueset "Office Visit": 'http://nih.gov'

// Global measurement timeframe parameter evaluated at runtime by the engine
parameter "Measurement Period" Interval<DateTime>
  default Interval[@2026-01-01T00:00:00, @2026-12-31T23:59:59]

context Patient

// 1. Initial Population: Female patients aged 50 to 74
define "Initial Population":
  Patient.gender = 'female'
    and AgeInYearsAt(start of "Measurement Period") between 50 and 74

// 2. Denominator: Must meet initial population and have an active office encounter
define "Denominator":
  "Initial Population"
    and exists (
      [Encounter: "Office Visit"] E
        where E.status = 'finished'
          and E.period during "Measurement Period"
    )

// 3. Numerator: Had a screening procedure performed during the timeframe
define "Numerator":
  exists (
    [Procedure: "Oid Breast Cancer Screening"] DiagnosticSample
      where DiagnosticSample.status = 'completed'
        and DiagnosticSample.performed during "Measurement Period"
  )
