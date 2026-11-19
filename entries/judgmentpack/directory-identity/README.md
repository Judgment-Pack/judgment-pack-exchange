# Directory identity

Prepare one directory identity's records as facts and evidence for an access review pack. The
records are in the shapes the Microsoft Graph API returns for Microsoft Entra objects: a user or a
service principal, its groups, roles, grants, sign-ins, audit events, risk, multifactor registration
and devices, and the organization's assigned plans.

This is an entry of kind `dialect`, dialect version 3, written against the pack
`https://example.com/judgment-packs/directory-identity` at version `0.1.0`, which is reproduced in
full at the end of this file. It proposes no decision of its own; the pack decides, and only after
a local review. Nothing here says that any record is true.

## The two inputs

**The case document** holds one identity. The caller reads each of the identity's records from
Microsoft Graph, joins them under that identity, and writes one member per record stream. Each
stream member carries exactly an `evidence` member, `"present"` or `"absent"`, and, when the
evidence is present, a `value` member holding the record as Graph returns it. One more member,
`streams`, is the caller's map from each stream's name to `{"state": "read"}` or
`{"state": "absent", "reason": R}`, where `R` is `licence`, `permission`, `read-failed` or
`not-applicable`. Every case target is copied (RFC 0018 §6.2), so every case fact is of class
`asserted`: the caller asserts it, and no receipt stands behind it.

**The organization source** is one `operation` source, `organization`, a `GET` of
`/v1.0/organization` through an `http` gateway source (the path is the binding's, version prefix
included). It is published unbound: platform `microsoft-graph`, operation `live`, shape `http`,
record `adapter-http`, with a `maxAge` of 3600 seconds. It binds to the gateway catalog's
microsoft-graph binding, from the gateway release that ships it. Its rule writes
`/tenant/licence/plans` from the first organization's `assignedPlans`, of class `record`, and the
evidence `organization-record`; a read that is not a `200` with assigned plans writes no fact and
reads that evidence as absent, with acquisition status `unknown`.

The request has no `query`: a `$select` member is a template form under RFC 0018 §4.1, so the
organization is read with Graph's default properties, which include `assignedPlans`.

## Facts

Each fact the pack reads lies at the pointer below. A fact name `a.b` is the object at `/a/b`.

| Fact | Pointer | Copied from (case) or read from (source) |
| --- | --- | --- |
| `identity.kind` | `/identity/kind` | `/user/value/userType` |
| `identity.enabled` | `/identity/enabled` | `/user/value/accountEnabled` |
| `identity.deleted` | `/identity/deleted` | `/user/value/deletedDateTime` |
| `identity.created_at` | `/identity/created_at` | `/user/value/createdDateTime` |
| `identity.synced_from_onprem` | `/identity/synced_from_onprem` | `/user/value/onPremisesSyncEnabled` |
| `identity.last_sign_in_at` | `/identity/last_sign_in_at` | `/user/value/signInActivity/lastSignInDateTime` |
| `identity.last_noninteractive_sign_in_at` | `/identity/last_noninteractive_sign_in_at` | `/user/value/signInActivity/lastNonInteractiveSignInDateTime` |
| `identity.groups` | `/identity/groups` | `/transitiveMemberOf/value` |
| `identity.privileged_roles` | `/identity/privileged_roles` | `/roleAssignments/value` |
| `identity.eligible_privileged_roles` | `/identity/eligible_privileged_roles` | `/roleEligibilitySchedules/value` |
| `identity.oauth_grants` | `/identity/oauth_grants` | `/oauth2PermissionGrants/value` |
| `identity.app_role_assignments` | `/identity/app_role_assignments` | `/appRoleAssignments/value` |
| `sp.credentials` | `/sp/credentials/passwordCredentials`, `/sp/credentials/keyCredentials` | `/servicePrincipal/value/passwordCredentials`, `/servicePrincipal/value/keyCredentials` |
| `sp.owners` | `/sp/owners` | `/servicePrincipal/value/owners` |
| `signin.event` | `/signin/event` | `/signIns/value` |
| `audit.event` | `/audit/event` | `/directoryAudits/value` |
| `risk.detection` | `/risk/detection` | `/riskDetections/value` |
| `identity.risk_level` | `/identity/risk_level` | `/riskyUser/value/riskLevel` |
| `identity.mfa` | `/identity/mfa` | `/registrationDetails/value` |
| `identity.device_ids` | `/identity/device_ids` | `/registeredDevices/value` |
| `tenant.licence` | `/tenant/licence/plans`, `/tenant/licence/streams` | the organization source's `/body/value/0/assignedPlans`; the case's `/streams` |

`sp.credentials` and `tenant.licence` are objects of two sibling targets each, so that no target is
a prefix of another (RFC 0018 §8.1). `tenant.licence` is the object at `/tenant/licence`: `plans`
is of class `record`, from the receipted organization read, and `streams` is of class `asserted`,
from the caller's map.

## Evidence

One evidence requirement per stream, copied from the stream's `evidence` member, and one from the
organization source.

| Evidence | Copied from |
| --- | --- |
| `user-record` | `/user/evidence` |
| `group-memberships` | `/transitiveMemberOf/evidence` |
| `role-assignments` | `/roleAssignments/evidence` |
| `role-eligibility` | `/roleEligibilitySchedules/evidence` |
| `oauth-grants` | `/oauth2PermissionGrants/evidence` |
| `app-role-assignments` | `/appRoleAssignments/evidence` |
| `service-principal-record` | `/servicePrincipal/evidence` |
| `sign-in-log` | `/signIns/evidence` |
| `directory-audit-log` | `/directoryAudits/evidence` |
| `risk-detections` | `/riskDetections/evidence` |
| `risk-state` | `/riskyUser/evidence` |
| `mfa-registration` | `/registrationDetails/evidence` |
| `registered-devices` | `/registeredDevices/evidence` |
| `organization-record` | the organization source's rule |

## Absent is not empty

A stream that was read and returned nothing has evidence `"present"` and a `value` of `[]`; its fact
is written as `[]`. A stream that was not read has evidence `"absent"` and no `value`; its facts are
not written, so a pack reads them as unknown, and its evidence reads absent. Why a stream is absent
is never inferred here: the caller states it in `streams`, which lands at `/tenant/licence/streams`.
The dialect never reads an absent stream as no data.

## What the caller prepares

The dialect copies; it does not select, filter or join. The caller prepares each record before the
case is written, and each fact below is only as narrow as that preparation:

- **The grouping per identity.** One case is one identity. The caller joins every stream to it,
  and filters each log and list to that identity.
- `identity.kind`: Graph's own `userType` spelling, `Member` or `Guest`, unchanged. It is written
  only for a user; a service principal has no user record, so the fact is not written.
- `identity.deleted`: `deletedDateTime` as Graph gives it, a timestamp or `null`, not a boolean.
- `identity.synced_from_onprem`: `onPremisesSyncEnabled` as Graph gives it: `true`, `false` for an
  identity no longer synchronized, or `null` for one never synchronized, so three values and not two.
- `identity.last_sign_in_at` and `identity.last_noninteractive_sign_in_at`: from the user record's
  `signInActivity`, which the caller selects with the user; the user stream carries it.
- `identity.groups`: the transitive memberships, as `transitiveMemberOf` returns them, not only the
  direct ones.
- `identity.privileged_roles` and `identity.eligible_privileged_roles`: the caller keeps only the
  assignments and eligibility schedules whose `roleDefinition` is privileged
  (`roleDefinition.isPrivileged` `true`), with `roleDefinition` expanded on each.
- `identity.oauth_grants` and `identity.app_role_assignments`: the grants and assignments the
  identity holds, as Graph lists them for that principal.
- `sp.credentials`: an object of two arrays, the service principal's `passwordCredentials` and
  `keyCredentials`, as metadata only (type, identifier and expiry); the fixtures carry no secret.
- `sp.owners`: the owners, expanded onto the service principal record (`$expand=owners`).
- `signin.event`, `audit.event` and `risk.detection`: the events for this identity over the window
  the caller chose, as Graph's sign-in, directory audit and risk detection lists return them.
- `identity.risk_level`: the `riskLevel` of the identity's risky-user record.
- `identity.mfa`: the identity's `userRegistrationDetails` object, whole.
- `identity.device_ids`: the device objects registered to the identity, as `registeredDevices`
  returns them, not bare identifiers; a pack reads an identifier at
  `/identity/device_ids/<n>/deviceId`.
- `tenant.licence`: the object at `/tenant/licence`. `plans` is the organization's `assignedPlans`
  from the receipted read; which plan covers which stream is the reader's categorisation, not the
  dialect's. `streams` is the caller's map of each stream's state and, when absent, its reason.
- **The evidence member.** The caller sets each stream's `evidence`, and its `streams` entry, from
  what the read did, and keeps the two consistent: a stream whose `streams[X].state` is `read`
  carries `X.evidence` `present`, and any other state carries `absent`. Nothing in the dialect
  checks that the two agree, so a reader relies on the caller for it.

## Fixtures

The fixtures are synthetic and written by hand, never recorded from a run. Every identifier is a
random GUID invented for the fixture, including the ids that stand for built-in role templates
and service plans, so none of them is a real directory's value. Every name is invented, every
domain is `example.com` or `example.org`, and every address is from a documentation range.

- `member-every-stream-read`: a member user with every stream that applies read; its OAuth grants
  stream is present and empty, so `identity.oauth_grants` is `[]` with evidence present.
- `guest-risk-and-mfa-parked`: a guest whose risk detections, risk state and multifactor
  registration were parked for licence; those facts are not written and that evidence reads absent,
  while its empty role assignments and devices are present as `[]`.
- `service-principal`: a service principal with a secret and a certificate and no owner, whose risk
  detections were not readable for permission and whose user-only streams (user, risky user,
  authentication-methods registration and registered devices) are not applicable.

Each fixture's `binding.json` binds the organization source to a stand-in input profile in its
`profiles.json`, whose public key belongs to a throwaway key pair made for these fixtures; its
private key was never kept. That profile, its key and its endpoint are the fixtures' and no
installation's: an installation binds its own profile, which changes the bound dialect's digest
and every preparation's `mappingDigest` (RFC 0018 §4.4).

## The pack

The minimal pack this dialect was written against. It reads every fact and every evidence
requirement above, is valid under Core 0.5.0, and its mapping coverage against this dialect is
complete. Its rules illustrate the facts' use; they are not a recommended access policy.

```json
{
  "specVersion": "0.5.0",
  "id": "https://example.com/judgment-packs/directory-identity",
  "version": "0.1.0",
  "title": "Directory identity access review",
  "description": "A minimal pack that reads every fact the directory-identity dialect prepares.",
  "decision": {
    "intent": "Decide whether one directory identity should go to an access reviewer.",
    "question": "Does this identity need an access review?"
  },
  "evidenceRequirements": [
    {
      "id": "user-record",
      "description": "The identity's user record, when the identity is a user.",
      "required": false,
      "kind": "fact"
    },
    {
      "id": "group-memberships",
      "description": "The identity's transitive group memberships.",
      "required": false,
      "kind": "fact"
    },
    {
      "id": "role-assignments",
      "description": "The identity's active privileged directory role assignments.",
      "required": false,
      "kind": "fact"
    },
    {
      "id": "role-eligibility",
      "description": "The identity's eligible privileged directory role assignments.",
      "required": false,
      "kind": "fact"
    },
    {
      "id": "oauth-grants",
      "description": "The delegated permission grants the identity holds.",
      "required": false,
      "kind": "fact"
    },
    {
      "id": "app-role-assignments",
      "description": "The application role assignments the identity holds.",
      "required": false,
      "kind": "fact"
    },
    {
      "id": "service-principal-record",
      "description": "The service principal record, when the identity is a service principal.",
      "required": false,
      "kind": "fact"
    },
    {
      "id": "sign-in-log",
      "description": "The identity's sign-in events for the review window.",
      "required": false,
      "kind": "fact"
    },
    {
      "id": "directory-audit-log",
      "description": "The directory audit events about the identity for the review window.",
      "required": false,
      "kind": "fact"
    },
    {
      "id": "risk-detections",
      "description": "The risk detections recorded for the identity.",
      "required": false,
      "kind": "fact"
    },
    {
      "id": "risk-state",
      "description": "The identity's current risk state.",
      "required": false,
      "kind": "fact"
    },
    {
      "id": "mfa-registration",
      "description": "The identity's authentication method registration details.",
      "required": false,
      "kind": "fact"
    },
    {
      "id": "registered-devices",
      "description": "The devices registered to the identity.",
      "required": false,
      "kind": "fact"
    },
    {
      "id": "organization-record",
      "description": "The organization record, read through a receipted gateway source.",
      "required": false,
      "kind": "fact"
    }
  ],
  "outcomes": [
    {
      "id": "review",
      "label": "Review",
      "description": "An access reviewer looks at this identity."
    },
    {
      "id": "no-review",
      "label": "No review indicated",
      "description": "No rule of this pack sends the identity to review."
    }
  ],
  "rules": [
    {
      "id": "guest-with-privileged-role",
      "description": "Review a guest that holds or is eligible for a privileged directory role.",
      "when": {
        "op": "all",
        "conditions": [
          {
            "op": "evidence-present",
            "evidenceRequirement": "user-record"
          },
          {
            "op": "fact",
            "path": "/identity/kind",
            "operator": "equals",
            "value": "Guest"
          },
          {
            "op": "any",
            "conditions": [
              {
                "op": "fact",
                "path": "/identity/privileged_roles",
                "operator": "not-equals",
                "value": []
              },
              {
                "op": "fact",
                "path": "/identity/eligible_privileged_roles",
                "operator": "not-equals",
                "value": []
              }
            ]
          }
        ]
      },
      "outcome": "review",
      "onUnknown": "escalate",
      "evidenceRequirementRefs": [
        "user-record",
        "role-assignments",
        "role-eligibility"
      ],
      "rationale": "A guest's privileged access is granted from outside its home directory."
    },
    {
      "id": "inactive-account-with-access",
      "description": "Review a disabled or deleted account that still holds access or shows activity.",
      "when": {
        "op": "all",
        "conditions": [
          {
            "op": "evidence-present",
            "evidenceRequirement": "user-record"
          },
          {
            "op": "any",
            "conditions": [
              {
                "op": "fact",
                "path": "/identity/enabled",
                "operator": "equals",
                "value": false
              },
              {
                "op": "not",
                "condition": {
                  "op": "fact",
                  "path": "/identity/deleted",
                  "operator": "equals",
                  "value": null
                }
              }
            ]
          },
          {
            "op": "any",
            "conditions": [
              {
                "op": "fact",
                "path": "/identity/groups",
                "operator": "not-equals",
                "value": []
              },
              {
                "op": "fact",
                "path": "/identity/app_role_assignments",
                "operator": "not-equals",
                "value": []
              },
              {
                "op": "fact",
                "path": "/identity/oauth_grants",
                "operator": "not-equals",
                "value": []
              },
              {
                "op": "fact",
                "path": "/signin/event",
                "operator": "not-equals",
                "value": []
              },
              {
                "op": "fact",
                "path": "/audit/event",
                "operator": "not-equals",
                "value": []
              }
            ]
          }
        ]
      },
      "outcome": "review",
      "onUnknown": "escalate",
      "evidenceRequirementRefs": [
        "user-record",
        "group-memberships",
        "app-role-assignments",
        "oauth-grants",
        "sign-in-log",
        "directory-audit-log"
      ],
      "rationale": "Access that outlives the account is access nobody is using on purpose."
    },
    {
      "id": "privileged-never-signed-in",
      "description": "Review a privileged account with a known creation time and no sign-in on record.",
      "when": {
        "op": "all",
        "conditions": [
          {
            "op": "evidence-present",
            "evidenceRequirement": "user-record"
          },
          {
            "op": "any",
            "conditions": [
              {
                "op": "fact",
                "path": "/identity/privileged_roles",
                "operator": "not-equals",
                "value": []
              },
              {
                "op": "fact",
                "path": "/identity/eligible_privileged_roles",
                "operator": "not-equals",
                "value": []
              }
            ]
          },
          {
            "op": "not",
            "condition": {
              "op": "fact",
              "path": "/identity/created_at",
              "operator": "equals",
              "value": null
            }
          },
          {
            "op": "fact",
            "path": "/identity/last_sign_in_at",
            "operator": "equals",
            "value": null
          },
          {
            "op": "fact",
            "path": "/identity/last_noninteractive_sign_in_at",
            "operator": "equals",
            "value": null
          }
        ]
      },
      "outcome": "review",
      "onUnknown": "escalate",
      "evidenceRequirementRefs": [
        "user-record",
        "role-assignments",
        "role-eligibility"
      ],
      "rationale": "A privileged role that is never used can be removed."
    },
    {
      "id": "synced-identity-with-privileged-role",
      "description": "Review a privileged role held by an identity synchronized from an on-premises directory.",
      "when": {
        "op": "all",
        "conditions": [
          {
            "op": "evidence-present",
            "evidenceRequirement": "user-record"
          },
          {
            "op": "fact",
            "path": "/identity/synced_from_onprem",
            "operator": "equals",
            "value": true
          },
          {
            "op": "fact",
            "path": "/identity/privileged_roles",
            "operator": "not-equals",
            "value": []
          }
        ]
      },
      "outcome": "review",
      "onUnknown": "escalate",
      "evidenceRequirementRefs": [
        "user-record",
        "role-assignments"
      ],
      "rationale": "A synchronized account carries the on-premises directory's exposure into the privileged role."
    },
    {
      "id": "privileged-without-mfa-registration",
      "description": "Review a privileged identity whose multifactor registration is missing or was not read.",
      "when": {
        "op": "all",
        "conditions": [
          {
            "op": "evidence-present",
            "evidenceRequirement": "user-record"
          },
          {
            "op": "any",
            "conditions": [
              {
                "op": "fact",
                "path": "/identity/privileged_roles",
                "operator": "not-equals",
                "value": []
              },
              {
                "op": "fact",
                "path": "/identity/eligible_privileged_roles",
                "operator": "not-equals",
                "value": []
              }
            ]
          },
          {
            "op": "any",
            "conditions": [
              {
                "op": "not",
                "condition": {
                  "op": "evidence-present",
                  "evidenceRequirement": "mfa-registration"
                }
              },
              {
                "op": "fact",
                "path": "/identity/mfa/isMfaRegistered",
                "operator": "equals",
                "value": false
              }
            ]
          }
        ]
      },
      "outcome": "review",
      "onUnknown": "escalate",
      "evidenceRequirementRefs": [
        "user-record",
        "role-assignments",
        "role-eligibility",
        "mfa-registration"
      ],
      "rationale": "Privileged access without a registered second factor, or without a reading of it, needs a person's look."
    },
    {
      "id": "elevated-risk",
      "description": "Review an identity whose current risk level is medium or high.",
      "when": {
        "op": "all",
        "conditions": [
          {
            "op": "evidence-present",
            "evidenceRequirement": "risk-state"
          },
          {
            "op": "fact",
            "path": "/identity/risk_level",
            "operator": "in",
            "value": [
              "medium",
              "high"
            ]
          }
        ]
      },
      "outcome": "review",
      "onUnknown": "escalate",
      "evidenceRequirementRefs": [
        "risk-state"
      ],
      "rationale": "The directory's own risk state says the identity may be compromised."
    },
    {
      "id": "detections-without-risk-state",
      "description": "Review an identity with risk detections whose current risk state was not read.",
      "when": {
        "op": "all",
        "conditions": [
          {
            "op": "evidence-present",
            "evidenceRequirement": "risk-detections"
          },
          {
            "op": "fact",
            "path": "/risk/detection",
            "operator": "not-equals",
            "value": []
          },
          {
            "op": "not",
            "condition": {
              "op": "evidence-present",
              "evidenceRequirement": "risk-state"
            }
          }
        ]
      },
      "outcome": "review",
      "onUnknown": "escalate",
      "evidenceRequirementRefs": [
        "risk-detections",
        "risk-state"
      ],
      "rationale": "Detections without the summary state leave whether they were remediated open."
    },
    {
      "id": "privileged-without-registered-device",
      "description": "Review a privileged user with no registered device.",
      "when": {
        "op": "all",
        "conditions": [
          {
            "op": "evidence-present",
            "evidenceRequirement": "user-record"
          },
          {
            "op": "evidence-present",
            "evidenceRequirement": "registered-devices"
          },
          {
            "op": "any",
            "conditions": [
              {
                "op": "fact",
                "path": "/identity/privileged_roles",
                "operator": "not-equals",
                "value": []
              },
              {
                "op": "fact",
                "path": "/identity/eligible_privileged_roles",
                "operator": "not-equals",
                "value": []
              }
            ]
          },
          {
            "op": "fact",
            "path": "/identity/device_ids",
            "operator": "equals",
            "value": []
          }
        ]
      },
      "outcome": "review",
      "onUnknown": "escalate",
      "evidenceRequirementRefs": [
        "user-record",
        "role-assignments",
        "role-eligibility",
        "registered-devices"
      ],
      "rationale": "Privileged access from no registered device is access from unmanaged machines."
    },
    {
      "id": "privileged-with-stream-parked-for-licence",
      "description": "Review a privileged identity whose risk or registration stream was parked for licence while the organization lists assigned plans.",
      "when": {
        "op": "all",
        "conditions": [
          {
            "op": "any",
            "conditions": [
              {
                "op": "fact",
                "path": "/identity/privileged_roles",
                "operator": "not-equals",
                "value": []
              },
              {
                "op": "fact",
                "path": "/identity/eligible_privileged_roles",
                "operator": "not-equals",
                "value": []
              }
            ]
          },
          {
            "op": "evidence-present",
            "evidenceRequirement": "organization-record"
          },
          {
            "op": "fact",
            "path": "/tenant/licence/plans",
            "operator": "not-equals",
            "value": []
          },
          {
            "op": "any",
            "conditions": [
              {
                "op": "all",
                "conditions": [
                  {
                    "op": "fact",
                    "path": "/tenant/licence/streams/riskyUser/state",
                    "operator": "equals",
                    "value": "absent"
                  },
                  {
                    "op": "fact",
                    "path": "/tenant/licence/streams/riskyUser/reason",
                    "operator": "equals",
                    "value": "licence"
                  }
                ]
              },
              {
                "op": "all",
                "conditions": [
                  {
                    "op": "fact",
                    "path": "/tenant/licence/streams/registrationDetails/state",
                    "operator": "equals",
                    "value": "absent"
                  },
                  {
                    "op": "fact",
                    "path": "/tenant/licence/streams/registrationDetails/reason",
                    "operator": "equals",
                    "value": "licence"
                  }
                ]
              }
            ]
          }
        ]
      },
      "outcome": "review",
      "onUnknown": "escalate",
      "evidenceRequirementRefs": [
        "role-assignments",
        "role-eligibility",
        "organization-record"
      ],
      "rationale": "A reviewer checks whether one of the listed plans covers the stream the caller parked."
    },
    {
      "id": "service-principal-credential-without-owner",
      "description": "Review a service principal that holds a secret or certificate and has no owner.",
      "when": {
        "op": "all",
        "conditions": [
          {
            "op": "evidence-present",
            "evidenceRequirement": "service-principal-record"
          },
          {
            "op": "any",
            "conditions": [
              {
                "op": "fact",
                "path": "/sp/credentials/passwordCredentials",
                "operator": "not-equals",
                "value": []
              },
              {
                "op": "fact",
                "path": "/sp/credentials/keyCredentials",
                "operator": "not-equals",
                "value": []
              }
            ]
          },
          {
            "op": "fact",
            "path": "/sp/owners",
            "operator": "equals",
            "value": []
          }
        ]
      },
      "outcome": "review",
      "onUnknown": "escalate",
      "evidenceRequirementRefs": [
        "service-principal-record"
      ],
      "rationale": "A credential nobody owns is a credential nobody rotates."
    }
  ],
  "fallbackOutcome": "no-review",
  "escalation": {
    "triggers": [
      "unknown"
    ],
    "target": {
      "kind": "human-role",
      "name": "Access reviewer"
    },
    "message": "A fact a rule needs could not be read; review the identity by hand."
  }
}
```
