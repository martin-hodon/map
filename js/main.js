// main.js -- the map's entry: every module, then their wiring in the order the one script had it
import * as style from "./style.js";
import * as state from "./state.js";
import * as geom from "./geom.js";
import * as history from "./history.js";
import * as view from "./view.js";
import * as labels from "./labels.js";
import * as offline from "./offline.js";
import * as data from "./data.js";
import * as lite from "./lite.js";
import * as search from "./search.js";
import * as flags from "./flags.js";
import * as select from "./select.js";
import * as groups from "./groups.js";
import * as game from "./game.js";
import * as ui from "./ui.js";

style.init();
state.init();
offline.init();
data.init();
groups.init();
game.init();
ui.init();
