# demo/

The same two captures the dissertation reports, placed where a live audience
can read the command off the screen.

    auditor scan demo/claude-code --spec demo/brief.yaml
    auditor scan demo/antigravity --spec demo/brief.yaml

One word apart. That is the whole demonstration: identical brief, identical
flags, and the only thing that changes is which agent produced the code.

The files are copied verbatim from data/raw/, which stays the source of record;
nothing here is re-scored or re-generated, and deleting this folder loses
nothing.
