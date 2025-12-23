using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

[System.Serializable]
public class PathJSONPoint { public float x; public float y; public float z; public Vector3 ToV3(){ return new Vector3(x,y,z); } }

[System.Serializable]
public class RunJSON { public string planner; public PathJSONPoint[] path; public float duration; }

[System.Serializable]
public class BenchmarkJSON { public RunJSON[] runs; }

/// <summary>
/// PathVisualization: reads a benchmark JSON (StreamingAssets) and draws paths with LineRenderers.
/// ADAPTIVE: green, RRT*: red, others: blue. Also animates a marker moving along the chosen path at speedMultiplier.
/// </summary>
public class PathVisualization : MonoBehaviour
{
    public string jsonFileName = "full_benchmark_results.json";
    public Material lineMaterial;
    public float lineWidth = 0.12f;
    public float speedMultiplier = 10f; // real-time x10

    private List<GameObject> animMarkers = new List<GameObject>();

    void Start()
    {
        LoadAndDraw();
    }

    void LoadAndDraw()
    {
        string path = Path.Combine(Application.streamingAssetsPath, jsonFileName);
        if (!File.Exists(path)) { Debug.LogError("Benchmark JSON not found: " + path); return; }
        string json = File.ReadAllText(path);
        BenchmarkJSON b = null;
        try { b = JsonUtility.FromJson<BenchmarkJSON>(json); }
        catch { Debug.LogWarning("Failed parse benchmark JSON"); }
        if (b == null || b.runs == null) { Debug.LogError("No runs in JSON"); return; }

        foreach (var run in b.runs)
        {
            if (run.path == null || run.path.Length < 2) continue;
            Vector3[] pts = new Vector3[run.path.Length];
            for (int i = 0; i < run.path.Length; i++) pts[i] = run.path[i].ToV3();

            GameObject go = new GameObject("Path_" + run.planner);
            var lr = go.AddComponent<LineRenderer>();
            lr.positionCount = pts.Length;
            lr.SetPositions(pts);
            lr.widthMultiplier = lineWidth;
            lr.material = lineMaterial != null ? lineMaterial : new Material(Shader.Find("Sprites/Default"));
            Color c = Color.blue;
            if (run.planner.ToUpper().Contains("ADAPTIVE")) c = Color.green;
            else if (run.planner.ToUpper().Contains("RRT")) c = Color.red;
            lr.startColor = lr.endColor = c;

            // animation marker
            GameObject marker = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            marker.transform.localScale = Vector3.one * (lineWidth * 2f);
            marker.GetComponent<Renderer>().material.color = c;
            marker.name = "Marker_" + run.planner;
            var poly = marker.AddComponent<PathAnimator>();
            poly.SetPath(pts, Mathf.Max(0.01f, run.duration) * speedMultiplier);
            animMarkers.Add(marker);
        }
    }
}

public class PathAnimator : MonoBehaviour
{
    Vector3[] path;
    float duration = 1f;
    float t = 0f;

    public void SetPath(Vector3[] p, float realTimeDuration)
    {
        path = p;
        duration = realTimeDuration;
        t = 0f;
    }
    void Update()
    {
        if (path == null || path.Length < 2) return;
        t += Time.deltaTime;
        float u = Mathf.Clamp01(t / duration);
        // simple interpolation along segments
        float totalLen = 0f; for (int i=0;i<path.Length-1;i++) totalLen += Vector3.Distance(path[i], path[i+1]);
        float target = u * totalLen;
        float acc = 0f;
        for (int i=0;i<path.Length-1;i++)
        {
            float seg = Vector3.Distance(path[i], path[i+1]);
            if (acc + seg >= target)
            {
                float local = (target - acc) / seg;
                transform.position = Vector3.Lerp(path[i], path[i+1], local);
                return;
            }
            acc += seg;
        }
        transform.position = path[path.Length-1];
    }
}
