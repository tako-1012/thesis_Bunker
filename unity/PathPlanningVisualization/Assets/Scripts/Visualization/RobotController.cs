using UnityEngine;
using System.Collections;
using System.Collections.Generic;

/// <summary>
/// ロボットの経路追従アニメーション
/// </summary>
public class RobotController : MonoBehaviour
{
    [Header("Robot Settings")]
    public GameObject robotModel;
    public float moveSpeed = 2f;
    public bool smoothRotation = true;
    public float rotationSpeed = 5f;
    
    [Header("Trail Settings")]
    public bool showTrail = true;
    public Material trailMaterial;
    public float trailWidth = 0.1f;
    
    private List<Vector3> pathToFollow;
    private int currentWaypointIndex = 0;
    private bool isMoving = false;
    private LineRenderer trailRenderer;
    
    void Start()
    {
        InitializeTrail();
    }
    
    void InitializeTrail()
    {
        if (!showTrail) return;
        
        GameObject trailObj = new GameObject("RobotTrail");
        trailObj.transform.parent = transform;
        
        trailRenderer = trailObj.AddComponent<LineRenderer>();
        trailRenderer.material = trailMaterial;
        trailRenderer.startWidth = trailWidth;
        trailRenderer.endWidth = trailWidth;
        trailRenderer.startColor = Color.yellow;
        trailRenderer.endColor = Color.yellow;
        trailRenderer.useWorldSpace = true;
        trailRenderer.positionCount = 0;
    }
    
    /// <summary>
    /// 経路に沿ってロボットを移動
    /// </summary>
    public void FollowPath(List<Vector3> path)
    {
        if (path == null || path.Count == 0)
        {
            Debug.LogWarning("Invalid path provided");
            return;
        }
        
        pathToFollow = new List<Vector3>(path);
        currentWaypointIndex = 0;
        
        // スタート位置に移動
        transform.position = pathToFollow[0];
        
        // トレイル初期化
        if (trailRenderer != null)
        {
            trailRenderer.positionCount = 0;
        }
        
        // 移動開始
        StartCoroutine(MoveAlongPath());
    }
    
    IEnumerator MoveAlongPath()
    {
        isMoving = true;
        
        while (currentWaypointIndex < pathToFollow.Count - 1)
        {
            Vector3 startPos = pathToFollow[currentWaypointIndex];
            Vector3 endPos = pathToFollow[currentWaypointIndex + 1];
            
            // 回転
            if (smoothRotation)
            {
                Vector3 direction = (endPos - startPos).normalized;
                if (direction != Vector3.zero)
                {
                    Quaternion targetRotation = Quaternion.LookRotation(direction);
                    while (Quaternion.Angle(transform.rotation, targetRotation) > 1f)
                    {
                        transform.rotation = Quaternion.Slerp(
                            transform.rotation,
                            targetRotation,
                            Time.deltaTime * rotationSpeed
                        );
                        yield return null;
                    }
                }
            }
            
            // 移動
            float distance = Vector3.Distance(startPos, endPos);
            float duration = distance / moveSpeed;
            float elapsed = 0f;
            
            while (elapsed < duration)
            {
                elapsed += Time.deltaTime;
                float t = elapsed / duration;
                
                transform.position = Vector3.Lerp(startPos, endPos, t);
                
                // トレイル更新
                UpdateTrail();
                
                yield return null;
            }
            
            transform.position = endPos;
            currentWaypointIndex++;
        }
        
        isMoving = false;
        Debug.Log("Robot reached goal!");
    }
    
    void UpdateTrail()
    {
        if (!showTrail || trailRenderer == null) return;
        
        trailRenderer.positionCount++;
        trailRenderer.SetPosition(trailRenderer.positionCount - 1, transform.position);
    }
    
    public void ResetRobot()
    {
        StopAllCoroutines();
        isMoving = false;
        currentWaypointIndex = 0;
        
        if (trailRenderer != null)
        {
            trailRenderer.positionCount = 0;
        }
    }
    
    public bool IsMoving()
    {
        return isMoving;
    }
}


