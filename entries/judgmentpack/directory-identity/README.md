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
evidence is present, a `value` member holding the record as Graph returns it. Three
members are not streams but values the caller prepares, each as `{"value": V}`: `kind`, `deleted` and
`licenceTier`. One more member, `streams`, is the caller's map from each stream's name to
`{"state": "read"}` or `{"state": "absent", "reason": R}`, where `R` is one of:

- `licence`: the directory's licence does not include the stream, or a read of it was refused for that
  reason.
- `permission`: the caller's credentials may not read the stream.
- `read-failed`: the read was tried and failed for another reason.
- `not-applicable`: the stream does not apply to this kind of identity.
- `home-directory`: the stream is evaluated in another directory, the identity's home directory, so
  this directory never has it. A guest's user risk is the case.

Every case target is copied (RFC 0018 §6.2), so every case fact is of class
`asserted`: the caller asserts it, and no receipt stands behind it.

**The organization source** is one `operation` source, `organization`, a `GET` of
`/v1.0/organization` through an `http` gateway source (the path is the binding's, version prefix
included). It is published unbound: platform `microsoft-graph`, operation `live`, shape `http`,
record `adapter-http`, with a `maxAge` of 3600 seconds. It binds to the gateway catalog's
microsoft-graph binding, from the gateway release that ships it. Its rule writes
`/directory/licence/plans` from the first organization's `assignedPlans`, of class `record`, and the
evidence `organization-record`; a read that is not a `200` with assigned plans writes no fact and
reads that evidence as absent, with acquisition status `unknown`.

The request has no `query`: a `$select` member is a template form under RFC 0018 §4.1, so the
organization is read with Graph's default properties, which include `assignedPlans`.

## Facts

Each fact the pack reads lies at the pointer below. A fact name `a.b` is the object at `/a/b`.

| Fact | Pointer | Copied from (case) or read from (source) |
| --- | --- | --- |
| `principal.kind` | `/principal/kind` | `/kind/value` |
| `principal.enabled` | `/principal/enabled` | `/user/value/accountEnabled` |
| `principal.deleted` | `/principal/deleted` | `/deleted/value` |
| `principal.created_at` | `/principal/created_at` | `/user/value/createdDateTime` |
| `principal.synced_from_onprem` | `/principal/synced_from_onprem` | `/user/value/onPremisesSyncEnabled` |
| `principal.last_sign_in_at` | `/principal/last_sign_in_at` | `/signInActivity/value/lastSignInDateTime` |
| `principal.last_noninteractive_sign_in_at` | `/principal/last_noninteractive_sign_in_at` | `/signInActivity/value/lastNonInteractiveSignInDateTime` |
| `principal.groups` | `/principal/groups` | `/transitiveMemberOf/value` |
| `principal.privileged_roles` | `/principal/privileged_roles` | `/roleAssignments/value` |
| `principal.eligible_privileged_roles` | `/principal/eligible_privileged_roles/directory`, `/principal/eligible_privileged_roles/groups` | `/roleEligibilitySchedules/value`, `/groupEligibility/value` |
| `principal.oauth_grants` | `/principal/oauth_grants` | `/oauth2PermissionGrants/value` |
| `principal.app_role_assignments` | `/principal/app_role_assignments` | `/appRoleAssignments/value` |
| `sp.credentials` | `/sp/credentials/passwordCredentials`, `/sp/credentials/keyCredentials` | `/servicePrincipal/value/passwordCredentials`, `/servicePrincipal/value/keyCredentials` |
| `sp.owners` | `/sp/owners` | `/servicePrincipal/value/owners` |
| `directory.sign_in_event` | `/directory/sign_in_event` | `/signIns/value` |
| `directory.audit_event` | `/directory/audit_event` | `/directoryAudits/value` |
| `directory.risk_detection` | `/directory/risk_detection` | `/riskDetections/value` |
| `principal.risk_level` | `/principal/risk_level` | `/riskyUser/value/riskLevel` |
| `principal.mfa` | `/principal/mfa` | `/registrationDetails/value` |
| `principal.device_ids` | `/principal/device_ids` | `/registeredDevices/value` |
| `directory.licence` | `/directory/licence/plans`, `/directory/licence/tier`, `/directory/licence/streams` | the organization source's `/body/value/0/assignedPlans`; the case's `/licenceTier/value`; the case's `/streams` |

`sp.credentials`, `principal.eligible_privileged_roles` and `directory.licence` are objects of sibling
targets, so that no target is a prefix of another (RFC 0018 §8.1). `directory.licence` is the object at
`/directory/licence`: `plans` is of class `record`, from the receipted organization read, and `tier`
and `streams` are of class `asserted`, from the caller. `principal.eligible_privileged_roles` has two
members, each with its own stream and evidence: `directory` is directory-role eligibility and `groups`
is eligibility for privileged-access groups.

## Evidence

One evidence requirement per stream, copied from the stream's `evidence` member, and one from the
organization source.

| Evidence | Copied from |
| --- | --- |
| `user-record` | `/user/evidence` |
| `group-memberships` | `/transitiveMemberOf/evidence` |
| `role-assignments` | `/roleAssignments/evidence` |
| `role-eligibility` | `/roleEligibilitySchedules/evidence` |
| `group-eligibility` | `/groupEligibility/evidence` |
| `oauth-grants` | `/oauth2PermissionGrants/evidence` |
| `app-role-assignments` | `/appRoleAssignments/evidence` |
| `service-principal-record` | `/servicePrincipal/evidence` |
| `sign-in-activity` | `/signInActivity/evidence` |
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
is never inferred here: the caller states it in `streams`, which lands at `/directory/licence/streams`.
The dialect never reads an absent stream as no data. The convention holds for each member of an object
fact alike: `principal.eligible_privileged_roles/directory` and `/groups` are each written as `[]`
when their stream was read and empty, and each is left unwritten, with its evidence absent, when its
stream was not read.

## What the caller prepares

The dialect copies; it does not select, filter or join. The caller prepares each record before the
case is written, and each fact below is only as narrow as that preparation:

- **The grouping per identity.** One case is one identity. The caller joins every stream to it,
  and filters each log and list to that identity.
- `principal.kind`: the caller's own classification, copied from the case's `/kind/value`, one of
  `member`, `guest`, `service_principal` or `managed_identity`. The caller writes it for every
  identity, service principals included; the dialect does not derive it from Graph's `userType`.
- `principal.deleted`: a boolean the caller prepares at `/deleted/value`: `true` when the identity is
  in deleted items or is gone from the directory (a delta read's `@removed`), `false` otherwise. It is
  not read from `deletedDateTime`.
- `principal.synced_from_onprem`: `onPremisesSyncEnabled` as Graph gives it: `true`, `false` for an
  identity no longer synchronized, or `null` for one never synchronized, so three values and not two.
- `principal.last_sign_in_at` and `principal.last_noninteractive_sign_in_at`: copied from their own
  stream, `signInActivity`, with its own evidence, `sign-in-activity`, and not from the user record.
  Selecting `signInActivity` needs a premium directory licence, and a directory without one refuses
  the whole user read when it is included. The caller therefore reads the user without it, reads
  `signInActivity` separately, and parks it with reason `licence` when that read is refused.
- `principal.groups`: the transitive memberships, as `transitiveMemberOf` returns them, not only the
  direct ones.
- `principal.privileged_roles` and `principal.eligible_privileged_roles/directory`: the caller keeps
  only the assignments and eligibility schedules whose `roleDefinition` is privileged
  (`roleDefinition.isPrivileged` `true`), with `roleDefinition` expanded on each.
- `principal.eligible_privileged_roles/groups`: from the caller-prepared `groupEligibility` stream,
  with evidence `group-eligibility`: the identity's eligibility schedules for privileged-access
  groups, as Graph's group eligibility schedules list them, kept to the groups the caller counts as
  privileged. It is a stream of its own, so it is absent, with evidence absent, when the caller did not
  read it.
- `principal.oauth_grants` and `principal.app_role_assignments`: the grants and assignments the
  identity holds, as Graph lists them for that principal.
- `sp.credentials`: an object of two arrays, the service principal's `passwordCredentials` and
  `keyCredentials`, as metadata only (type, identifier and expiry); the fixtures carry no secret.
- `sp.owners`: the owners, expanded onto the service principal record (`$expand=owners`).
- `directory.sign_in_event`, `directory.audit_event` and `directory.risk_detection`: the events for
  this identity over the window the caller chose, as Graph's sign-in, directory audit and risk
  detection lists return them.
- `principal.risk_level`: the `riskLevel` of the identity's risky-user record. A guest's user risk is
  evaluated in the guest's home directory, so for a guest the caller parks this stream with reason
  `home-directory`.
- `principal.mfa`: the identity's `userRegistrationDetails` object, whole.
- `principal.device_ids`: the device objects registered to the identity, as `registeredDevices`
  returns them, not bare identifiers; a pack reads an identifier at
  `/principal/device_ids/<n>/deviceId`.
- `directory.licence`: the object at `/directory/licence`. `plans` is the organization's
  `assignedPlans` from the receipted read; which plan covers which stream is the reader's
  categorisation, not the dialect's. `tier` is the caller's licence category for the directory, copied
  from `/licenceTier/value`: `free`, `p1` or `p2`, of class `asserted`. `streams` is the caller's map
  of each stream's state and, when absent, its reason.
- **The evidence member.** The caller sets each stream's `evidence`, and its `streams` entry, from
  what the read did, and keeps the two consistent: a stream whose `streams[X].state` is `read`
  carries `X.evidence` `present`, and any other state carries `absent`. Nothing in the dialect
  checks that the two agree, so a reader relies on the caller for it.

## Fixtures

The fixtures are synthetic and written by hand, never recorded from a run. Every identifier is a
random GUID invented for the fixture, including the ids that stand for built-in role templates
and service plans, so none of them is a real directory's value. Every name is invented, every
domain is `example.com` or `example.org`, and every address is from a documentation range.

- `member-every-stream-read`: a member user in a directory of licence category `p2`, with every
  stream that applies read, `signInActivity` and the group eligibility stream included; its OAuth
  grants stream is present and empty, so `principal.oauth_grants` is `[]` with evidence present.
- `guest-risk-and-mfa-parked`: a guest in a directory of category `free`. Its `signInActivity`,
  risk detections and multifactor registration streams were parked for `licence`, and its risk-state
  stream for `home-directory`, because a guest's user risk is evaluated in its home directory; those
  facts are not written and that evidence reads absent. Its empty role assignments, group eligibility
  and devices are present as `[]`.
- `service-principal`: a service principal, kind `service_principal`, in a directory of category
  `p2`, with a secret and a certificate and no owner, whose risk detections were not readable for
  permission and whose user-only streams (user, sign-in activity, group eligibility, risky user,
  authentication-methods registration and registered devices) are not applicable; its
  `principal.eligible_privileged_roles/groups` is therefore not written.

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
      "id": "group-eligibility",
      "description": "The identity's eligibility for privileged-access groups.",
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
      "id": "sign-in-activity",
      "description": "The identity's last sign-in times, read as their own stream.",
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
            "path": "/principal/kind",
            "operator": "equals",
            "value": "guest"
          },
          {
            "op": "any",
            "conditions": [
              {
                "op": "fact",
                "path": "/principal/privileged_roles",
                "operator": "not-equals",
                "value": []
              },
              {
                "op": "fact",
                "path": "/principal/eligible_privileged_roles/directory",
                "operator": "not-equals",
                "value": []
              },
              {
                "op": "fact",
                "path": "/principal/eligible_privileged_roles/groups",
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
        "role-eligibility",
        "group-eligibility"
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
                "path": "/principal/enabled",
                "operator": "equals",
                "value": false
              },
              {
                "op": "fact",
                "path": "/principal/deleted",
                "operator": "equals",
                "value": true
              }
            ]
          },
          {
            "op": "any",
            "conditions": [
              {
                "op": "fact",
                "path": "/principal/groups",
                "operator": "not-equals",
                "value": []
              },
              {
                "op": "fact",
                "path": "/principal/app_role_assignments",
                "operator": "not-equals",
                "value": []
              },
              {
                "op": "fact",
                "path": "/principal/oauth_grants",
                "operator": "not-equals",
                "value": []
              },
              {
                "op": "fact",
                "path": "/directory/sign_in_event",
                "operator": "not-equals",
                "value": []
              },
              {
                "op": "fact",
                "path": "/directory/audit_event",
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
            "op": "evidence-present",
            "evidenceRequirement": "sign-in-activity"
          },
          {
            "op": "any",
            "conditions": [
              {
                "op": "fact",
                "path": "/principal/privileged_roles",
                "operator": "not-equals",
                "value": []
              },
              {
                "op": "fact",
                "path": "/principal/eligible_privileged_roles/directory",
                "operator": "not-equals",
                "value": []
              },
              {
                "op": "fact",
                "path": "/principal/eligible_privileged_roles/groups",
                "operator": "not-equals",
                "value": []
              }
            ]
          },
          {
            "op": "not",
            "condition": {
              "op": "fact",
              "path": "/principal/created_at",
              "operator": "equals",
              "value": null
            }
          },
          {
            "op": "fact",
            "path": "/principal/last_sign_in_at",
            "operator": "equals",
            "value": null
          },
          {
            "op": "fact",
            "path": "/principal/last_noninteractive_sign_in_at",
            "operator": "equals",
            "value": null
          }
        ]
      },
      "outcome": "review",
      "onUnknown": "escalate",
      "evidenceRequirementRefs": [
        "user-record",
        "sign-in-activity",
        "role-assignments",
        "role-eligibility",
        "group-eligibility"
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
            "path": "/principal/synced_from_onprem",
            "operator": "equals",
            "value": true
          },
          {
            "op": "fact",
            "path": "/principal/privileged_roles",
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
                "path": "/principal/privileged_roles",
                "operator": "not-equals",
                "value": []
              },
              {
                "op": "fact",
                "path": "/principal/eligible_privileged_roles/directory",
                "operator": "not-equals",
                "value": []
              },
              {
                "op": "fact",
                "path": "/principal/eligible_privileged_roles/groups",
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
                "path": "/principal/mfa/isMfaRegistered",
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
        "group-eligibility",
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
            "path": "/principal/risk_level",
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
            "path": "/directory/risk_detection",
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
                "path": "/principal/privileged_roles",
                "operator": "not-equals",
                "value": []
              },
              {
                "op": "fact",
                "path": "/principal/eligible_privileged_roles/directory",
                "operator": "not-equals",
                "value": []
              },
              {
                "op": "fact",
                "path": "/principal/eligible_privileged_roles/groups",
                "operator": "not-equals",
                "value": []
              }
            ]
          },
          {
            "op": "fact",
            "path": "/principal/device_ids",
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
        "group-eligibility",
        "registered-devices"
      ],
      "rationale": "Privileged access from no registered device is access from unmanaged machines."
    },
    {
      "id": "privileged-with-stream-parked-for-licence",
      "description": "Review a privileged identity whose risk or registration stream was parked for licence while the organization lists assigned plans and the caller's licence category is free or p1.",
      "when": {
        "op": "all",
        "conditions": [
          {
            "op": "any",
            "conditions": [
              {
                "op": "fact",
                "path": "/principal/privileged_roles",
                "operator": "not-equals",
                "value": []
              },
              {
                "op": "fact",
                "path": "/principal/eligible_privileged_roles/directory",
                "operator": "not-equals",
                "value": []
              },
              {
                "op": "fact",
                "path": "/principal/eligible_privileged_roles/groups",
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
            "path": "/directory/licence/plans",
            "operator": "not-equals",
            "value": []
          },
          {
            "op": "fact",
            "path": "/directory/licence/tier",
            "operator": "in",
            "value": [
              "free",
              "p1"
            ]
          },
          {
            "op": "any",
            "conditions": [
              {
                "op": "all",
                "conditions": [
                  {
                    "op": "fact",
                    "path": "/directory/licence/streams/riskyUser/state",
                    "operator": "equals",
                    "value": "absent"
                  },
                  {
                    "op": "fact",
                    "path": "/directory/licence/streams/riskyUser/reason",
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
                    "path": "/directory/licence/streams/registrationDetails/state",
                    "operator": "equals",
                    "value": "absent"
                  },
                  {
                    "op": "fact",
                    "path": "/directory/licence/streams/registrationDetails/reason",
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
        "group-eligibility",
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
