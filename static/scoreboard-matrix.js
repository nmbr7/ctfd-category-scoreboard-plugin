
const graph = $("#score-graph");
const table1 = $("#scoreboard tbody");
const config = {
  displaylogo: false,
  responsive: true
};
const layout = {
  title: "Top 10 " + (window.userMode === "teams" ? "Teams" : "Users"),
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  hovermode: "closest",
  xaxis: {
    showgrid: false,
    showspikes: true
  },
  yaxis: {
    showgrid: false,
    showspikes: true
  },
  legend: {
    orientation: "h"
  }
};

function updateScores(){
  CTFd.api.get_scoreboard_list().then(response => {
      const teams = response.data;
      table.empty();
      for (let i = 0; i < teams.length; i++) {
        // Encode the team name
        const row = ["<tr>","<td>",i+1,"</td>",'<td><a href="">',teams[i].name,'</a></td>','<td class="chalmark">',teams[i].score,'</td>','</tr>'].join("");
        table1.append(row);
    }
  });
}

function createGraph() {
  CTFd.api.get_scoreboard_detail({ count: 10 }).then(response => {
    const places = response.data;

    const teams = Object.keys(places);
    const traces = [];
    if (teams.length === 0) {
      // Replace spinner
      graph.html(
        '<h3 class="opacity-50 text-center w-100 justify-content-center align-self-center">No solves yet</h3>'
      );
      return;
    }
    for (let i = 0; i < teams.length; i++) {
      const team_score = [];
      const times = [];
      for (let j = 0; j < places[teams[i]]["solves"].length; j++) {
        team_score.push(places[teams[i]]["solves"][j].value);
        const date = Moment(places[teams[i]]["solves"][j].date);
        times.push(date.toDate());
      }
      const trace = {
        x: times,
        y: cumulativeSum(team_score),
        mode: "lines+markers",
        name: places[teams[i]]["name"],
        marker: {
          color: colorHash(places[teams[i]]["name"] + places[teams[i]]["id"])
        },
        line: {
          color: colorHash(places[teams[i]]["name"] + places[teams[i]]["id"])
        }
      };
      traces.push(trace);
    }

    traces.sort((a, b) => {
      const score_diff = b["y"][b["y"].length - 1] - a["y"][a["y"].length - 1];
      if (!score_diff) {
        return a["x"][a["x"].length - 1] - b["x"][b["x"].length - 1];
      }
      return score_diff;
    });

    graph.empty(); // Remove spinners
    graph[0].fn = "CTFd_scoreboard_" + new Date().toISOString().slice(0, 19);
    Plotly.newPlot(graph[0], traces, layout, config);
  });
}

function updateGraph() {
  CTFd.api.get_scoreboard_detail({ count: 10 }).then(response => {
    const places = response.data;

    const teams = Object.keys(places);
    const traces = [];
    if (teams.length === 0) {
      return;
    }
    //console.log(places);
    for (let i = 0; i < teams.length; i++) {
      const team_score = [];
      const times = [];
      for (let j = 0; j < places[teams[i]]["solves"].length; j++) {
        team_score.push(places[teams[i]]["solves"][j].value);
        const date = Moment(places[teams[i]]["solves"][j].date);
        //console.log(date);
        times.push(date.toDate());
      }
      const trace = {
        x: times,
        y: cumulativeSum(team_score),
        mode: "lines+markers",
        name: places[teams[i]]["name"],
        marker: {
          color: colorHash(places[teams[i]]["name"] + places[teams[i]]["id"])
        },
        line: {
          color: colorHash(places[teams[i]]["name"] + places[teams[i]]["id"])
        }
      };
      traces.push(trace);
    }

    traces.sort((a, b) => {
      const score_diff = b["y"][b["y"].length - 1] - a["y"][a["y"].length - 1];
      if (!score_diff) {
        return a["x"][a["x"].length - 1] - b["x"][b["x"].length - 1];
      }
      return score_diff;
    });

    Plotly.react(graph[0], traces, layout, config);
  });
}

function update() {
    location.reload();
    updateScores();
    updateGraph();

}
$(() => {
  setInterval(update, 60000); // Update scores every 5 minutes
  createGraph();
  updateGraph();
});
