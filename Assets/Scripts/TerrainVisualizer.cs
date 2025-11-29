using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// TerrainVisualizer: TerrainData から地形メッシュを生成し、コストマップで頂点色を設定
/// </summary>
public class TerrainVisualizer : MonoBehaviour
{
    public Material terrainMaterial;

    private MeshFilter meshFilter;
    private MeshRenderer meshRenderer;

    void Awake()
    {
        meshFilter = gameObject.AddComponent<MeshFilter>();
        meshRenderer = gameObject.AddComponent<MeshRenderer>();
        if (terrainMaterial != null)
            meshRenderer.material = terrainMaterial;
    }

    /// <summary>
    /// TerrainData から地形メッシュを生成
    /// </summary>
    public void GenerateTerrain(TerrainData terrainData)
    {
        if (terrainData == null || terrainData.gridSize == null || terrainData.gridSize.Count < 2)
        {
            Debug.LogError("Invalid TerrainData");
            return;
        }

        int width = terrainData.gridSize[0];
        int height = terrainData.gridSize[1];
        float resolution = terrainData.resolution;

        Mesh mesh = new Mesh();
        mesh.name = "TerrainMesh";

        List<Vector3> vertices = new List<Vector3>();
        List<Color> colors = new List<Color>();
        List<int> triangles = new List<int>();

        // 頂点と色の生成
        for (int y = 0; y < height; y++)
        {
            for (int x = 0; x < width; x++)
            {
                float worldX = x * resolution;
                float worldY = y * resolution;
                float cost = terrainData.costMap[y][x];
                float heightZ = cost * 2.0f; // コストを高さに変換（スケール調整）

                vertices.Add(new Vector3(worldX, worldY, heightZ));
                colors.Add(GetColorFromCost(cost));
            }
        }

        // 三角形インデックスの生成
        for (int y = 0; y < height - 1; y++)
        {
            for (int x = 0; x < width - 1; x++)
            {
                int topLeft = y * width + x;
                int topRight = topLeft + 1;
                int bottomLeft = (y + 1) * width + x;
                int bottomRight = bottomLeft + 1;

                // 1つ目の三角形
                triangles.Add(topLeft);
                triangles.Add(bottomLeft);
                triangles.Add(topRight);

                // 2つ目の三角形
                triangles.Add(topRight);
                triangles.Add(bottomLeft);
                triangles.Add(bottomRight);
            }
        }

        mesh.vertices = vertices.ToArray();
        mesh.colors = colors.ToArray();
        mesh.triangles = triangles.ToArray();
        mesh.RecalculateNormals();

        meshFilter.mesh = mesh;

        Debug.Log($"Terrain mesh generated: {vertices.Count} vertices, {triangles.Count / 3} triangles");
    }

    /// <summary>
    /// コスト値から頂点色を決定
    /// </summary>
    private Color GetColorFromCost(float cost)
    {
        // 0.0: 緑, 0.5: 黄, 1.0: 赤
        if (cost < 0.5f)
        {
            // 緑→黄
            return Color.Lerp(Color.green, Color.yellow, cost * 2f);
        }
        else
        {
            // 黄→赤
            return Color.Lerp(Color.yellow, Color.red, (cost - 0.5f) * 2f);
        }
    }
}
