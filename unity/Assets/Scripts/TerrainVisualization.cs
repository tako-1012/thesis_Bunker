using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

[System.Serializable]
public class Vec3JSON { public float x; public float y; public float z; public Vector3 ToV3(){ return new Vector3(x,y,z); } }

[System.Serializable]
public class PointCloudJSON { public Vec3JSON[] points; public int width; public int height; }

/// <summary>
/// TerrainVisualization: reads a JSON point-cloud (placed in StreamingAssets) and creates either a heightmap mesh (if width/height provided)
/// or a point-cloud visualization (fallback). Colors vertices by slope: <10° green, 10-20° yellow, >20° red.
/// </summary>
public class TerrainVisualization : MonoBehaviour
{
    public string jsonFileName = "demo_small_moderate.json";
    public float scale = 1f;
    public Material meshMaterial;
    public GameObject pointPrefab; // small sphere prefab for fallback

    private void Start()
    {
        StartCoroutine(LoadAndBuild());
    }

    IEnumerator LoadAndBuild()
    {
        string path = Path.Combine(Application.streamingAssetsPath, jsonFileName);
        string json = "";
        if (path.Contains("://") || path.Contains("https://"))
        {
            using (var www = new UnityEngine.Networking.UnityWebRequest(path))
            {
                www.downloadHandler = new UnityEngine.Networking.DownloadHandlerBuffer();
                yield return www.SendWebRequest();
                json = www.downloadHandler.text;
            }
        }
        else
        {
            if (!File.Exists(path)) { Debug.LogError("JSON not found: " + path); yield break; }
            json = File.ReadAllText(path);
        }

        PointCloudJSON pc = null;
        try { pc = JsonUtility.FromJson<PointCloudJSON>(json); }
        catch (System.Exception e) { Debug.LogWarning("Json parse failed: " + e.Message); }

        if (pc == null || pc.points == null || pc.points.Length == 0) { Debug.LogError("No points in JSON"); yield break; }

        if (pc.width > 1 && pc.height > 1 && pc.width * pc.height == pc.points.Length)
        {
            BuildHeightmap(pc);
        }
        else
        {
            // fallback: spawn point prefabs
            BuildPointCloud(pc);
        }
    }

    void BuildHeightmap(PointCloudJSON pc)
    {
        int w = pc.width;
        int h = pc.height;
        Vector3[] verts = new Vector3[w * h];
        Color[] colors = new Color[verts.Length];
        int[] tris = new int[(w - 1) * (h - 1) * 6];

        for (int y = 0; y < h; y++) for (int x = 0; x < w; x++)
        {
            var p = pc.points[y * w + x].ToV3() * scale;
            verts[y * w + x] = new Vector3(p.x, p.z, p.y); // adapt depending on source coord
        }

        int ti = 0;
        for (int y = 0; y < h - 1; y++) for (int x = 0; x < w - 1; x++)
        {
            int i = y * w + x;
            tris[ti++] = i;
            tris[ti++] = i + w;
            tris[ti++] = i + 1;

            tris[ti++] = i + 1;
            tris[ti++] = i + w;
            tris[ti++] = i + w + 1;
        }

        Mesh m = new Mesh();
        m.vertices = verts;
        m.triangles = tris;
        m.RecalculateNormals();

        Vector3[] normals = m.normals;
        for (int i = 0; i < verts.Length; i++)
        {
            float angle = Vector3.Angle(normals[i], Vector3.up);
            colors[i] = ColorBySlope(angle);
        }
        m.colors = colors;

        GameObject go = new GameObject("TerrainMesh");
        var mf = go.AddComponent<MeshFilter>();
        var mr = go.AddComponent<MeshRenderer>();
        mf.mesh = m;
        if (meshMaterial != null) mr.material = meshMaterial; else mr.material = new Material(Shader.Find("Standard"));
    }

    void BuildPointCloud(PointCloudJSON pc)
    {
        for (int i = 0; i < pc.points.Length; i++)
        {
            Vector3 p = pc.points[i].ToV3() * scale;
            Vector3 pos = new Vector3(p.x, p.z, p.y);
            GameObject s = null;
            if (pointPrefab != null) s = Instantiate(pointPrefab, pos, Quaternion.identity, this.transform);
            else { s = GameObject.CreatePrimitive(PrimitiveType.Sphere); s.transform.position = pos; s.transform.localScale = Vector3.one * 0.05f; s.transform.parent = this.transform; }
            // approximate normal by looking at neighbours not implemented in fallback
            var rend = s.GetComponent<Renderer>(); if (rend) rend.material.color = Color.green;
        }
    }

    Color ColorBySlope(float angle)
    {
        if (angle < 10f) return Color.green;
        if (angle < 20f) return Color.yellow;
        return Color.red;
    }
}
