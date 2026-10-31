// Page and text styling shared by the invoices and the lesson reports, so
// the PDFs look like they belong together. Apply it to a whole document
// with `#show: style`.
//
// Sizes carry over from the original HTML/CSS design at 1px = 0.75pt

#let style(doc) = {
  set page(paper: "a4", margin: 37.5pt, fill: rgb("#f1f8f3"))
  set text(font: ("Helvetica", "Arial"), size: 12pt)
  show heading.where(level: 1): set text(size: 18pt, fill: rgb("#333333"))
  show heading.where(level: 1): set block(below: 30pt)
  show heading.where(level: 2): set text(size: 15pt)
  show heading.where(level: 2): set block(below: 15pt)
  show link: it => underline(text(fill: rgb("#0000ee"), it))
  doc
}
