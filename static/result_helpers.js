// Racer result predicates shared by the TV dashboard and the announcer results page.
(function (root) {
  function timeOf(racer) {
    return (racer.Time || "").trim().toUpperCase();
  }

  function isFinished(racer) {
    var t = timeOf(racer);
    return Boolean(t) && t !== "-" && t !== "DNS" && t !== "DNF" && t !== "DSQ";
  }

  function hasResult(racer) {
    var t = timeOf(racer);
    return t === "DNS" || t === "DNF" || t === "DSQ" || isFinished(racer);
  }

  function isUnfinished(racer) {
    var t = timeOf(racer);
    return t === "" || t === "-";
  }

  function shouldDisplayRacer(racer, includeUnfinished) {
    return hasResult(racer) || (includeUnfinished === true && isUnfinished(racer));
  }

  var api = {
    isFinished: isFinished,
    hasResult: hasResult,
    isUnfinished: isUnfinished,
    shouldDisplayRacer: shouldDisplayRacer,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.ResultHelpers = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
