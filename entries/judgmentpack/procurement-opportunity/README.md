# Public procurement opportunities

Prepare public procurement facts without deciding eligibility or bid priority.

This is an unbound research preset. It proposes no decision policy and is not an executable workflow. A local installation must choose a pack, bind its own AI and web profiles, review the target paths, and explicitly authorize research.

Supply one case with a `request` string, for example:

```json
{
  "request": "Prepare facts for the open procurement notice titled Example Laundry Services published by Example Hospital in Ontario. Use the original public notice, retain its exact URL and deadline, and distinguish purchasing information pages from active opportunities."
}
```

Each run prepares one research record about the one opportunity the request names or describes. Run separately for each opportunity; importing a preset neither selects opportunities nor decides eligibility or bid priority. The request is reviewed task scope. Model output cannot broaden it.

The definition requests `gemini-2.5-flash` and answer, search and page capabilities. The installation must bind profiles declaring that exact model and those capabilities. To use another model, review and save a local derivative with a new canonical identity before acquisition. Credentials and connection IDs stay local.

The prepared `/research` object preserves each field’s status, typed value and response citations. Missing, stale or conflicting fields stay explicit; the notice's own status is the `notice_status` field. No value is coerced or manufactured. A local pack must interpret these fields and any evidence-availability requirements explicitly; successful preparation does not establish factual truth.

All derived targets admit generated data only. A supporting quote does not upgrade a generated value to record-class evidence. Access restrictions remain in force on every source, including procurement portals that require sign-in.

As a preset, this entry has no pack binding, executable fixtures or verification claim. Its form and canonical identity are checked by the catalog; preparation and decision tests belong to the reviewed local configuration.
