# What this standard is called, and why it changed

**Decided 23 November 2026.** This supersedes every earlier use of "KYA" as a
normative name. It changes no reading, no figure and no published result.

## The problem, stated as an assessor would find it

Someone evaluating this work in November 2026 found:

- two hash-chained receipt formats, one signed and one not;
- both called KYA;
- by one author;
- and an unrelated **DIF KYA-OS**, an identity and authorisation framework with
  a published spec, already using the acronym.

None of that is a product family. It reads as someone who has not decided, and
a standards body does not call it breadth. The draft paper had already noticed
and was writing "Know Your AgenticAI" out in full to dodge the clash, which is
a patch in prose for a problem in the spec.

## The actual error

One name was doing three different jobs. Separating them costs nothing that has
been published and removes the collision completely.

| Job | Name | Where it appears |
|---|---|---|
| Market category | **Know Your Agent** | writing, site, sales conversations |
| Normative standard | **Agent Constitution Standard**, id `agent-constitution` | the spec, a receipt's `standard` field, the media type, committee submissions |
| Tools | the existing package names | PyPI, unchanged |

This is how the market being borrowed from already works. "Know Your Customer"
is a category; the standards under it are FATF Recommendations and JMLSG
guidance. Nobody writes a specification called KYC. The category is what makes
a compliance buyer understand the offer in four words, and it is the wrong kind
of name for a normative document.

`constitution` was already the right word and was already in use here, in
`specs/kya_constitution_v1.yaml` and in a published post. The five elements are
constitutional concepts: bounded powers, separation of duty, a record, an
amendment path, named accountability. Nobody in this field owns the term.

## Rules, so this cannot drift again

1. **"Know Your Agent" never appears in a specification, a schema, a field
   value or a media type.** It is prose.
2. **"KYA" is not used alone in any new writing.** Where it has to appear, for
   a file name or a package already published, it is a legacy identifier and
   this file is the explanation.
3. **Any public use of the category carries the disambiguation:** *Know Your
   Agent is unrelated to DIF's KYA-OS, which addresses identity and
   authorisation.* That sentence is cheap and it stops a reviewer concluding
   you are claiming someone else's work.
4. **One normative name per artefact.** A receipt says `agent-constitution`.

## What does not change

- The five elements, their `basis`, and every reading already produced.
- Published figures. The study ran against `kya/1` and nothing here touches it.
- PyPI package names. A tool is not a standard, and renaming a published
  package to chase a naming decision costs users and buys nothing.
- Receipts already issued. `agent-constitution/1` declares
  `supersedes: {standard: kya, version: 1}`, and a verifier accepts the old
  identity. A receipt produced against `kya/1` was true when it was made, and
  renaming a standard must not invalidate a record somebody is holding.

## What changes

- `specs/agent_constitution_v1.yaml` is the normative spec. `kya/1` is retained
  as a frozen alias, because CLAUDE.md forbids editing a spec mid-experiment
  and because the published study ran against it.
- New receipts name `agent-constitution`.
- The draft paper's normative sections take the new name. Its title may keep
  the category.
- One receipt envelope replaces two. See `docs/RECEIPT_ENVELOPE.md`.

## The honest part

This is a decision about words. It removes a reason to dismiss the work and it
adds no evidence that anybody wants the work. The adoption position is
unchanged and is recorded where it can be checked: no stars, no forks, no
outside contributor, no registry entry, and a falsifiable test with a date on
it. Naming is a precondition for being taken seriously by a committee. It is
not traction and must not be reported as any.
