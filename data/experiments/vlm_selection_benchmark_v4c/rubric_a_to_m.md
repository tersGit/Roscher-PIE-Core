# Neutral ground-truth rubric A-M

Score factual and spatial image dependence, not prose fluency. A response receives credit only for facts visibly supported by the unlabelled generated control.

| ID | Criterion |
|---|---|
| A | Red rectangle recognized as a rectangle, not a square. |
| B | Blue circle correctly located right of red rectangle. |
| C | Yellow triangle correctly located below red rectangle. |
| D | Green rectangle correctly located below blue circle. |
| E | Road recognized at the bottom/front of schematic. |
| F | Driveway recognized as the connection from road to house. |
| G | House and red roof recognized. |
| H | Pool recognized right of house. |
| I | Neighbour building recognized left of house. |
| J | Tree recognized above pool. |
| K | Boundary recognized as surrounding the scene. |
| L | Multi-view differences: pool only first view; driveway only second view; shared house/road. |
| M | Hallucination restraint and UNKNOWN discipline: no invented features; explicit unknown/non-visible only when warranted. |

Pass requires correct E-L relationships, no material hallucination, and materially better image-dependent spatial behavior than the 256M baseline. A fluent list of shapes is insufficient.
