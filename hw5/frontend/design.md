# Campus Customs operations dashboard design

The dashboard is designed as an operations desk rather than a generic chat screen. A dark ink-and-pink masthead establishes the product identity, while the main workspace uses warm paper, white cards, and restrained borders so operational facts remain easy to scan.

The left rail keeps the three tickets visible and makes the selected ticket explicit. The main column follows the order a reviewer needs: ticket facts, live status, agent activity, payment controls, and the database snapshot. Agent events use a vertical stream with agent names, event types, and short event summaries so delegation and MCP evidence are understandable without reading raw logs.

Financial state is intentionally prominent in the header. Pending requests use amber status styling, while the approval control is separate from the run action. The UI asks for an approver name, disables duplicate clicks while a request is in flight, and refreshes cash and ticket state from the backend after approval. Reset is explicit and confirmed.

The layout collapses the ticket rail into a horizontal selector on narrow screens and turns the two-column evidence panels into a single column. Empty, loading, and error states are first-class so the interface never implies that an agent run or payment happened when the API has not confirmed it.

