# People at a selected company

Research public professional roles at one explicitly selected company.

This is an unbound research preset. It proposes no decision policy and is not an executable workflow. A local installation must choose a pack, bind its own AI and web profiles, review the target paths, and explicitly authorize research.

Supply one case with a `request` string, for example:

```json
{
  "request": "At the selected company Example Claims, find a public professional responsible for operations or intake. Verify current role from an accessible company biography or professional source. Keep missing details unknown; do not infer personal email addresses."
}
```

Each run prepares one research record about one person; if several people match, the fields answer not-found and the request is narrowed. Run separately for each selected company or person; importing a preset neither selects records nor authorizes outreach. The request is reviewed task scope. Model output cannot broaden it.

The definition requests `gemini-2.5-flash` and answer, search and page capabilities. The installation must bind profiles declaring that exact model and those capabilities. To use another model, review and save a local derivative with a new canonical identity before acquisition. Credentials and connection IDs stay local.

The prepared `/research` object preserves each field’s status, typed value and response citations. Missing, stale or conflicting fields stay explicit. No value is coerced or manufactured. A local pack must interpret these fields and any evidence-availability requirements explicitly; successful preparation does not establish factual truth.

All derived targets admit generated data only. A supporting quote does not upgrade a generated value to record-class evidence. Access restrictions remain in force, including on professional-network sites.

As a preset, this entry has no pack binding, executable fixtures or verification claim. Its form and canonical identity are checked by the catalog; preparation and decision tests belong to the reviewed local configuration.
