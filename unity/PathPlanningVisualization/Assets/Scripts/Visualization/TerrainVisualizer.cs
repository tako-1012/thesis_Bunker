using UnityEngine;
using System.Collections.Generic;

/// <summary>
/// 3D地形の可視化システム
/// 占有グリッドと勾配グリッドを視覚化
/// </summary>
public class TerrainVisualizer : MonoBehaviour
{
    [Header("Grid Settings")]
    public Vector3Int gridSize = new Vector3Int(100, 100, 30);
    public float voxelSize = 0.1f;
    public Vector3 minBound = new Vector3(-5f, -5f, 0f);
    
    [Header("Visualization Settings")]
    public Material obstacleMaterial;
    public Material groundMaterial;
    public Material slopeMaterial;
    public bool showObstacles = true;
    public bool showSlopes = true;
    public float obstacleAlpha = 0.7f;
    
    [Header("Performance")]
    public int maxVisibleVoxels = 10000;
    public bool useInstancing = true;
    
    private GameObject terrainContainer;
    private List<GameObject> voxelObjects = new List<GameObject>();
    private byte[,,] occupancyGrid;
    private float[,,] slopeGrid;
    
    void Start()
    {
        InitializeContainer();
    }
    
    void InitializeContainer()
    {
        terrainContainer = new GameObject("TerrainContainer");
        terrainContainer.transform.parent = transform;
    }
    
    /// <summary>
    /// 占有グリッドを設定
    /// </summary>
    public void SetOccupancyGrid(byte[,,] grid)
    {
        occupancyGrid = grid;
        if (showObstacles)
        {
            VisualizeObstacles();
        }
    }
    
    /// <summary>
    /// 勾配グリッドを設定
    /// </summary>
    public void SetSlopeGrid(float[,,] grid)
    {
        slopeGrid = grid;
        if (showSlopes)
        {
            VisualizeSlopes();
        }
    }
    
    void VisualizeObstacles()
    {
        ClearVoxels();
        
        if (occupancyGrid == null) return;
        
        int count = 0;
        
        for (int x = 0; x < gridSize.x && count < maxVisibleVoxels; x++)
        {
            for (int y = 0; y < gridSize.y && count < maxVisibleVoxels; y++)
            {
                for (int z = 0; z < gridSize.z && count < maxVisibleVoxels; z++)
                {
                    if (occupancyGrid[x, y, z] == 1)
                    {
                        CreateVoxel(x, y, z, obstacleMaterial);
                        count++;
                    }
                }
            }
        }
        
        Debug.Log($"Visualized {count} obstacle voxels");
    }
    
    void VisualizeSlopes()
    {
        // 地面の勾配を色で表現
        // 実装: グラデーションテクスチャを生成
        CreateGroundPlane();
    }
    
    void CreateVoxel(int x, int y, int z, Material material)
    {
        Vector3 worldPos = GridToWorld(x, y, z);
        
        GameObject voxel = GameObject.CreatePrimitive(PrimitiveType.Cube);
        voxel.transform.position = worldPos;
        voxel.transform.localScale = Vector3.one * voxelSize;
        voxel.transform.parent = terrainContainer.transform;
        
        var renderer = voxel.GetComponent<Renderer>();
        renderer.material = material;
        
        // 半透明設定
        Color color = renderer.material.color;
        color.a = obstacleAlpha;
        renderer.material.color = color;
        
        voxelObjects.Add(voxel);
    }
    
    void CreateGroundPlane()
    {
        GameObject ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
        ground.name = "GroundPlane";
        ground.transform.parent = terrainContainer.transform;
        ground.transform.position = minBound;
        ground.transform.localScale = new Vector3(
            gridSize.x * voxelSize * 0.1f,
            1f,
            gridSize.y * voxelSize * 0.1f
        );
        
        ground.GetComponent<Renderer>().material = groundMaterial;
    }
    
    Vector3 GridToWorld(int x, int y, int z)
    {
        return new Vector3(
            x * voxelSize + minBound.x,
            z * voxelSize + minBound.z,  // UnityはY-up
            y * voxelSize + minBound.y
        );
    }
    
    void ClearVoxels()
    {
        foreach (var voxel in voxelObjects)
        {
            Destroy(voxel);
        }
        voxelObjects.Clear();
    }
    
    public void ToggleObstacles(bool show)
    {
        showObstacles = show;
        if (show && occupancyGrid != null)
        {
            VisualizeObstacles();
        }
        else
        {
            ClearVoxels();
        }
    }
}


