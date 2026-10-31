// A lesson report, styled like the invoices. The report itself is Typst
// markup, written by `generate-invoices --reports` and edited by hand; it
// is included from the path in `sys.inputs.report`, so that errors in it
// point to its own lines. This file only does layout.
#import "style.typ": style
#show: style

#set par(spacing: 15pt)
#set list(spacing: 10pt)

#v(37.5pt)
#include sys.inputs.report
