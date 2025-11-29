using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// PathVisualizer: 複数経路をLineRendererで可視化
/// </summary>
public class PathVisualizer : MonoBehaviour
{
    public Material pathMaterial;
    public float lineWidth = 0.1f;

    private Dictionary<string, GameObject> pathObjects = new Dictionary<string, GameObject>();

    /// <summary>
    /// 経路データを可視化
    /// </summary>
    public void VisualizePaths(Dictionary<string, PathData> paths)
    {
        ClearPaths();

        foreach (var kvp in paths)
        {
            string plannerName = kvp.Key;
            PathData pathData = kvp.Value;

            if (!pathData.success || pathData.path == null || pathData.path.Count < 2)
            {
                Debug.LogWarning($"Skipping {plannerName}: path invalid");
                continue;
            }

            GameObject pathObj = new GameObject($"Path_{plannerName}");
            pathObj.transform.SetParent(transform);

            LineRenderer lineRenderer = pathObj.AddComponent<LineRenderer>();
            lineRenderer.material = pathMaterial;
            lineRenderer.positionCount = pathData.path.Count;

            // 色設定
            Color pathColor = HexToColor(pathData.color);
            lineRenderer.startColor = pathColor;
            lineRenderer.endColor = pathColor;

            // 太さ設定（ADAPTIVEは2倍）
            float width = lineWidth;
            if (plannerName == "ADAPTIVE")
            {
                width *= 2f;
            }
            lineRenderer.startWidth = width;
            lineRenderer.endWidth = width;

            // 経路座標設定（地形より0.2m上）
            for (int i = 0; i < pathData.path.Count; i++)
            {
                List<float> point = pathData.path[i];
                Vector3 position = new Vector3(point[0], point[1], point[2] + 0.2f);
                lineRenderer.SetPosition(i, position);
            }

            pathObjects[plannerName] = pathObj;

            Debug.Log($"Path visualized: {plannerName} ({pathData.path.Count} points, {pathData.computationTime:F2}s)");
        }
    }

    /// <summary>
    /// 既存経路を削除
    /// </summary>
    public void ClearPaths()
    {
        foreach (var pathObj in pathObjects.Values)
        {
            Destroy(pathObj);
        }
        pathObjects.Clear();
    }

    /// <summary>
    /// #RRGGBB 形式のカラーコードを Color に変換
    /// </summary>
    private Color HexToColor(string hex)
    {
        if (string.IsNullOrEmpty(hex)) return Color.white;
        hex = hex.Replace("#", "");
        if (hex.Length != 6) return Color.white;

        byte r = byte.Parse(hex.Substring(0, 2), System.Globalization.NumberStyles.HexNumber);
        byte g = byte.Parse(hex.Substring(2, 2), System.Globalization.NumberStyles.HexNumber);
        byte b = byte.Parse(hex.Substring(4, 2), System.Globalization.NumberStyles.HexNumber);

        return new Color32(r, g, b, 255);
    }
}
