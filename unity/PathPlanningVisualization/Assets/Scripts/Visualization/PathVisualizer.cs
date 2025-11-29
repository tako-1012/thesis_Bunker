using UnityEngine;
using System.Collections.Generic;

/// <summary>
/// 計画経路の可視化システム
/// LineRendererを使用した滑らかな経路表示
/// </summary>
public class PathVisualizer : MonoBehaviour
{
    [Header("Path Settings")]
    public Material pathMaterial;
    public Color pathColor = Color.blue;
    public float pathWidth = 0.15f;
    public bool animatePath = true;
    public float animationSpeed = 2f;
    
    [Header("Waypoint Settings")]
    public GameObject waypointPrefab;
    public bool showWaypoints = true;
    public float waypointSize = 0.1f;
    
    [Header("Start/Goal Settings")]
    public GameObject startMarkerPrefab;
    public GameObject goalMarkerPrefab;
    public Color startColor = Color.green;
    public Color goalColor = Color.red;
    
    private LineRenderer pathLine;
    private List<GameObject> waypoints = new List<GameObject>();
    private GameObject startMarker;
    private GameObject goalMarker;
    private float animationProgress = 0f;
    private List<Vector3> currentPath = new List<Vector3>();
    
    void Start()
    {
        InitializeLineRenderer();
    }
    
    void InitializeLineRenderer()
    {
        GameObject lineObj = new GameObject("PathLine");
        lineObj.transform.parent = transform;
        
        pathLine = lineObj.AddComponent<LineRenderer>();
        pathLine.material = pathMaterial;
        pathLine.startColor = pathColor;
        pathLine.endColor = pathColor;
        pathLine.startWidth = pathWidth;
        pathLine.endWidth = pathWidth;
        pathLine.useWorldSpace = true;
        pathLine.positionCount = 0;
    }
    
    /// <summary>
    /// 経路を設定して可視化
    /// </summary>
    public void SetPath(List<Vector3> pathPoints)
    {
        ClearPath();
        
        if (pathPoints == null || pathPoints.Count == 0)
        {
            Debug.LogWarning("Empty path provided");
            return;
        }
        
        currentPath = new List<Vector3>(pathPoints);
        
        // LineRendererに経路を設定
        pathLine.positionCount = pathPoints.Count;
        pathLine.SetPositions(pathPoints.ToArray());
        
        // ウェイポイント表示
        if (showWaypoints)
        {
            CreateWaypoints(pathPoints);
        }
        
        // アニメーション初期化
        if (animatePath)
        {
            animationProgress = 0f;
            StartCoroutine(AnimatePathReveal());
        }
        
        Debug.Log($"Path visualized with {pathPoints.Count} waypoints");
    }
    
    /// <summary>
    /// スタート・ゴールマーカー設定
    /// </summary>
    public void SetStartGoal(Vector3 start, Vector3 goal)
    {
        ClearMarkers();
        
        // スタートマーカー
        startMarker = CreateMarker(start, startColor, "Start");
        
        // ゴールマーカー
        goalMarker = CreateMarker(goal, goalColor, "Goal");
    }
    
    GameObject CreateMarker(Vector3 position, Color color, string name)
    {
        GameObject marker = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        marker.name = name;
        marker.transform.position = position;
        marker.transform.localScale = Vector3.one * 0.3f;
        marker.transform.parent = transform;
        
        var renderer = marker.GetComponent<Renderer>();
        renderer.material.color = color;
        
        return marker;
    }
    
    void CreateWaypoints(List<Vector3> points)
    {
        foreach (var point in points)
        {
            GameObject waypoint = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            waypoint.transform.position = point;
            waypoint.transform.localScale = Vector3.one * waypointSize;
            waypoint.transform.parent = transform;
            
            var renderer = waypoint.GetComponent<Renderer>();
            renderer.material.color = pathColor;
            
            waypoints.Add(waypoint);
        }
    }
    
    System.Collections.IEnumerator AnimatePathReveal()
    {
        float duration = pathLine.positionCount / animationSpeed;
        float elapsed = 0f;
        
        while (elapsed < duration)
        {
            elapsed += Time.deltaTime;
            float progress = Mathf.Clamp01(elapsed / duration);
            
            // グラデーション効果
            Gradient gradient = new Gradient();
            gradient.SetKeys(
                new GradientColorKey[] {
                    new GradientColorKey(pathColor, 0f),
                    new GradientColorKey(pathColor, progress),
                    new GradientColorKey(Color.clear, progress)
                },
                new GradientAlphaKey[] {
                    new GradientAlphaKey(1f, 0f),
                    new GradientAlphaKey(1f, progress),
                    new GradientAlphaKey(0f, progress)
                }
            );
            
            pathLine.colorGradient = gradient;
            
            yield return null;
        }
        
        // アニメーション完了後、完全表示
        pathLine.startColor = pathColor;
        pathLine.endColor = pathColor;
    }
    
    void ClearPath()
    {
        pathLine.positionCount = 0;
        
        foreach (var waypoint in waypoints)
        {
            Destroy(waypoint);
        }
        waypoints.Clear();
    }
    
    void ClearMarkers()
    {
        if (startMarker != null) Destroy(startMarker);
        if (goalMarker != null) Destroy(goalMarker);
    }
    
    public void ToggleWaypoints(bool show)
    {
        showWaypoints = show;
        foreach (var waypoint in waypoints)
        {
            waypoint.SetActive(show);
        }
    }
    
    public List<Vector3> GetPathPoints()
    {
        return currentPath;
    }
}


