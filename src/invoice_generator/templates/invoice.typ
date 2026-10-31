// Invoices, one page each. Everything is formatted for display in Python
// and arrives as JSON in `sys.inputs.data`:
//
// {
//   "period": "January 2024",
//   "bank": {"name": ..., "sort_code": ..., "account_number": ..., "bank": ...},
//   "contact": {"mobile": ..., "email": ...},
//   "invoices": [
//     {
//       "student": "Alice",
//       "sessions": [{"date": "15/01/2024", "time": "10:00 until 11:00 (1 hour)"}],
//       "total_time": "1 hour",
//       "rate": "£50.00/hour",
//       "amount_owed": "£50.00"
//     }
//   ]
// }
#import "style.typ": style
#show: style

#let data = json(bytes(sys.inputs.data))

// Sizes carry over from the original HTML/CSS design at 1px = 0.75pt
#let grey = rgb("#c6c6c6")
#let rule = 1.5pt + grey

// Two-column table with a rounded border and straight inner lines
#let bordered(..cells) = block(
  stroke: rule,
  radius: 7.5pt,
  clip: true,
  table(
    columns: 2,
    inset: (x: 7.5pt, y: 5pt),
    stroke: (x, y) => (
      left: if x > 0 { rule },
      top: if y > 0 { rule },
    ),
    ..cells,
  ),
)

#let borderless(..cells) = table(
  columns: 2,
  stroke: none,
  inset: 3.75pt,
  align: left,
  ..cells,
)

#for (i, invoice) in data.invoices.enumerate() {
  if i > 0 { pagebreak() }
  v(37.5pt)
  [= #invoice.student invoice for #data.period]
  grid(
    columns: (55%, 45%),
    // Vertical rule between the columns
    grid.vline(x: 1, stroke: rule),
    [
      == Sessions
      #bordered(..invoice.sessions.map(s => (s.date, s.time)).flatten())
      #v(15pt)
      #bordered(
        [Total time], invoice.total_time,
        [Rate], invoice.rate,
        strong[Amount owed], strong(invoice.amount_owed),
      )
    ],
    [
      #align(center)[== Payment]
      #align(center, borderless(
        [Name:], data.bank.name,
        [Sort code:], data.bank.sort_code,
        [Account no:], data.bank.account_number,
        [Bank:], data.bank.bank,
      ))
      #v(22.5pt)
      #align(center, borderless(
        [Mobile:], data.contact.mobile,
        [Email:], link("mailto:" + data.contact.email, data.contact.email),
      ))
    ],
  )
}
