# Company research

Prepare company facts for a locally reviewed qualification pack.

This is an unbound research preset. It proposes no decision policy and is not an executable workflow. A local installation must choose a pack, bind its own AI and web profiles, review the target paths, and explicitly authorize research.

Supply one case with a `request` string, for example:

```json
{
  "request": "Which companies in Ontario provide claims handling services? Find public company facts, including company name, verified website, locations, dated employee range and documented intake channels. Do not infer internal routing from a generic contact form."
}
```

Each run prepares one research record. Run separately for each selected company or person; importing a preset neither selects records nor authorizes outreach. The request is reviewed task scope. Model output cannot broaden it.

The definition requests `gemini-2.5-flash` and answer, search and page capabilities. The installation must bind profiles declaring that exact model and those capabilities. To use another model, review and save a local derivative with a new canonical identity before acquisition. Credentials and connection IDs stay local.

The prepared `/research` object preserves each field’s status, typed value and response citations. Missing, stale or conflicting fields stay explicit. Integer counts remain JSON integers; range endpoints are decimal strings under the Dialect contract. No value is coerced or manufactured. A local pack must interpret these fields and any evidence-availability requirements explicitly; successful preparation does not establish factual truth.

All derived targets admit generated data only. A supporting quote does not upgrade a generated value to record-class evidence. Access restrictions remain in force, including on professional-network sites.

As a preset, this entry has no pack binding, executable fixtures or verification claim. Its form and canonical identity are checked by the catalog; preparation and decision tests belong to the reviewed local configuration.
